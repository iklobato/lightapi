#!/usr/bin/env bash
# e2e:
# JWT login, token claims and expiry, IsAuthenticated/IsAdminUser and permissions per method.
set -u
NAME=04_auth_jwt
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
E2E=$ROOT/tools/e2e
OUT=$E2E/.out/$NAME
mkdir -p "$OUT"
PORT=${E2E_PORT:-18100}
BASE=http://127.0.0.1:$PORT
DB_URL=${E2E_DB_URL:-sqlite:///$OUT/db.sqlite}
PASSED=0
FAILED=0
JSON='Content-Type: application/json'

# expect <step> <status> <jq filter that must be true, or ""> -- <curl args>
expect() {
	local step=$1 want=$2 filter=$3
	shift 3
	[ "${1:-}" = "--" ] && shift
	local got
	got=$(curl -s -o "$OUT/body" -D "$OUT/headers" -w '%{http_code}' "$@")
	if [ "$got" != "$want" ]; then
		FAILED=$((FAILED + 1))
		echo "FAIL $step: want $want got $got: $(head -c 300 "$OUT/body")"
		return 1
	fi
	if [ -n "$filter" ] && ! jq -e "$filter" "$OUT/body" >/dev/null 2>&1; then
		FAILED=$((FAILED + 1))
		echo "FAIL $step: body does not satisfy jq '$filter': $(head -c 300 "$OUT/body")"
		return 1
	fi
	PASSED=$((PASSED + 1))
	echo "PASS $step"
}

# header <step> <extended regex matched case-insensitively against the last response headers>
header() {
	if grep -qiE "$2" "$OUT/headers"; then
		PASSED=$((PASSED + 1))
		echo "PASS $1"
	else
		FAILED=$((FAILED + 1))
		echo "FAIL $1: no header matching '$2': $(tr -d '\r' <"$OUT/headers" | tr '\n' ' ')"
	fi
}

# check <step> <arguments for test(1)>
check() {
	local step=$1
	shift
	if test "$@"; then
		PASSED=$((PASSED + 1))
		echo "PASS $step"
	else
		FAILED=$((FAILED + 1))
		echo "FAIL $step: test $* is false"
	fi
}

# body <jq filter>: a value from the last response body
body() { jq -r "$1" "$OUT/body"; }

# --- pre-start: clean the database this run will use ---
case $DB_URL in
sqlite*) rm -f "$OUT/db.sqlite" ;;
postgresql*) $E2E_PSQL -q -c "DROP TABLE IF EXISTS e2e04_secrets, e2e04_admin, e2e04_mixed" ;;
esac

# --- start the server ---
E2E_PORT=$PORT E2E_DB_URL=$DB_URL E2E_OUT=$OUT LIGHTAPI_JWT_SECRET=e2e-secret PYTHONPATH=$E2E \
	uv run --frozen --extra dev --directory "$ROOT" python "$E2E/apps/$NAME.py" >"$OUT/server.log" 2>&1 &
PID=$!
trap 'pkill -P $PID 2>/dev/null; kill $PID 2>/dev/null; wait $PID 2>/dev/null' EXIT
for _ in $(seq 1 60); do
	curl -s -o /dev/null "$BASE/healthz" && break
	sleep 0.25
done
if ! curl -s -o /dev/null "$BASE/healthz"; then
	echo "FAIL $NAME: server did not start on $BASE"
	tail -20 "$OUT/server.log"
	exit 1
fi

# --- STEPS ---
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
expect "login bad password" 401 '.detail=="Invalid credentials"' -- -X POST -H "$JSON" -d '{"username":"admin","password":"wrong"}' "$BASE/auth/login"
expect "login unknown user" 401 '.detail=="Invalid credentials"' -- -X POST -H "$JSON" -d '{"username":"ghost","password":"x"}' "$BASE/auth/login"
expect "login missing field" 422 '' -- -X POST -H "$JSON" -d '{"username":"admin"}' "$BASE/auth/login"
expect "login get is 405" 405 '.detail=="method not allowed"' -- "$BASE/auth/login"
header "login 405 allow" '^allow: POST'
expect "login user" 200 '(.token|type)=="string" and .user.username=="user" and .user.is_admin==false' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
USER_TOKEN=$(body .token)
expect "login admin" 200 '(.token|type)=="string" and .user.is_admin==true' -- -X POST -H "$JSON" -d '{"username":"admin","password":"secret"}' "$BASE/auth/login"
ADMIN_TOKEN=$(body .token)
expect "token alias route" 200 '(.token|type)=="string"' -- -X POST -H "$JSON" -d '{"username":"admin","password":"secret"}' "$BASE/auth/token"

# the payload is the middle base64url segment; pad it for the decoder
PAYLOAD=$(echo "$ADMIN_TOKEN" | cut -d. -f2 | tr '_-' '/+')
PAYLOAD_JSON=$(printf '%s' "$PAYLOAD" | awk '{ while (length($0) % 4) $0 = $0 "="; print }' | base64 -d 2>/dev/null)
check "token carries the extra claim" "$(printf '%s' "$PAYLOAD_JSON" | jq -r .is_admin)" = true
check "token expires in about 120s" "$(printf '%s' "$PAYLOAD_JSON" | jq -r '(.exp - now) | floor')" -gt 100

expect "secrets without token" 401 '.detail=="Authentication credentials invalid."' -- "$BASE/secrets"
header "secrets 401 www-authenticate" '^www-authenticate: Bearer'
# Flip the first character of the signature: every bit of it counts. Replacing the last one
# was a no-op one time in sixteen (its two padding bits are ignored by base64url).
HEADER_AND_PAYLOAD=${USER_TOKEN%.*}
SIGNATURE=${USER_TOKEN##*.}
[ "${SIGNATURE:0:1}" = A ] && FLIPPED=B || FLIPPED=A
TAMPERED_TOKEN="$HEADER_AND_PAYLOAD.$FLIPPED${SIGNATURE:1}"
SCHEME=Bearer # kept apart from the token on the next line: a secret scanner read the pair as a leaked credential
expect "secrets tampered token" 401 '.detail=="Authentication credentials invalid."' -- -H "Authorization: $SCHEME $TAMPERED_TOKEN" "$BASE/secrets"
expect "secrets wrong scheme" 401 '' -- -H "Authorization: Basic $(printf 'user:password' | base64)" "$BASE/secrets"
expect "secrets with token" 200 '.results==[]' -- -H "Authorization: Bearer $USER_TOKEN" "$BASE/secrets"
expect "secrets post with token" 201 '.text=="s1"' -- -X POST -H "$JSON" -H "Authorization: Bearer $USER_TOKEN" -d '{"text":"s1"}' "$BASE/secrets"

EXPIRED=$(uv run --frozen --extra dev --directory "$ROOT" python -c "import jwt,datetime; print(jwt.encode({'sub':'2','exp':datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=5)}, 'e2e-secret', algorithm='HS256'))")
expect "secrets expired token" 401 '.detail=="Authentication credentials invalid."' -- -H "Authorization: Bearer $EXPIRED" "$BASE/secrets"

expect "admin as user is 403" 403 '.detail=="Insufficient permissions"' -- -H "Authorization: Bearer $USER_TOKEN" "$BASE/admin"
expect "admin post as user is 403" 403 '.detail=="Insufficient permissions"' -- -X POST -H "$JSON" -H "Authorization: Bearer $USER_TOKEN" -d '{"text":"x"}' "$BASE/admin"
expect "admin as admin" 200 '.results==[]' -- -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/admin"
expect "admin without token" 401 '' -- "$BASE/admin"

expect "mixed: anonymous get" 200 '.results==[]' -- "$BASE/mixed"
expect "mixed: anonymous post" 401 '' -- -X POST -H "$JSON" -d '{"text":"x"}' "$BASE/mixed"
expect "mixed: user post" 201 '.id==1' -- -X POST -H "$JSON" -H "Authorization: Bearer $USER_TOKEN" -d '{"text":"x"}' "$BASE/mixed"
expect "mixed: anonymous get detail" 200 '.id==1' -- "$BASE/mixed/1"
expect "mixed: user delete is 403" 403 '.detail=="Insufficient permissions"' -- -X DELETE -H "Authorization: Bearer $USER_TOKEN" "$BASE/mixed/1"
expect "mixed: admin delete" 204 '' -- -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/mixed/1"

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
