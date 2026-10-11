#!/usr/bin/env bash
# e2e:
# The fourth login in a minute is 429 with the rate-limit headers; CRUD routes are not limited.
set -u
NAME=13_rate_limit
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

# --- pre-start: clean the database this run will use ---
case $DB_URL in
sqlite*) rm -f "$OUT/db.sqlite" ;;
postgresql*) $E2E_PSQL -q -c "DROP TABLE IF EXISTS e2e13_secrets; DROP TABLE IF EXISTS e2e13_public" ;;
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
expect "login 1" 200 '' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
expect "login 2 (bad) counts too" 401 '' -- -X POST -H "$JSON" -d '{"username":"user","password":"nope"}' "$BASE/auth/login"
expect "login 3" 200 '' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
expect "login 4 is limited" 429 '.detail=="Too many requests. Please try again later."' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
header "retry-after" '^retry-after: [0-9]+'
header "x-ratelimit-limit" '^x-ratelimit-limit: 3'
header "x-ratelimit-remaining" '^x-ratelimit-remaining: 0'
header "x-ratelimit-reset" '^x-ratelimit-reset: [0-9]+'
expect "login 5 still limited" 429 '' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
: >"$OUT/public.codes"
for _ in $(seq 1 10); do curl -s -o /dev/null -w '%{http_code}\n' "$BASE/public" >>"$OUT/public.codes"; done
check "crud route is not limited" "$(sort -u "$OUT/public.codes" | tr -d '\n')" = 200

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
