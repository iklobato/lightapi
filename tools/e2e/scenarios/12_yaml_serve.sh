#!/usr/bin/env bash
# e2e:
# `lightapi serve` on a YAML document (sync and async), defaults, per-method auth, the CLI.
set -u
NAME=12_yaml_serve
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
E2E=$ROOT/tools/e2e
OUT=$E2E/.out/$NAME
mkdir -p "$OUT"
PORT=${E2E_PORT:-18100}
BASE=http://127.0.0.1:$PORT
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

# --- pre-start: fresh databases, documents with this run's paths ---
rm -f "$OUT/db.sqlite" "$OUT/async.sqlite"
sed "s|@DB@|sqlite:///$OUT/db.sqlite|" "$E2E/configs/12_yaml_serve.yaml" >"$OUT/config.yaml"
sed "s|@DB@|sqlite+aiosqlite:///$OUT/async.sqlite|" "$E2E/configs/12_yaml_async.yaml" >"$OUT/async.yaml"

# --- start the two servers through the CLI ---
serve() { # serve <config> <port> <log>
	LIGHTAPI_CONFIG=$1 LIGHTAPI_PORT=$2 LIGHTAPI_HOST=127.0.0.1 LIGHTAPI_JWT_SECRET=e2e-secret PYTHONPATH=$E2E \
		uv run --frozen --extra dev --directory "$ROOT" python -m lightapi serve >"$3" 2>&1 &
	echo $!
}
PID=$(serve "$OUT/config.yaml" "$PORT" "$OUT/server.log")
APORT=$((PORT + 1))
ABASE=http://127.0.0.1:$APORT
APID=$(serve "$OUT/async.yaml" "$APORT" "$OUT/async.server.log")
trap 'pkill -P $PID $APID 2>/dev/null; kill $PID $APID 2>/dev/null; wait $PID $APID 2>/dev/null' EXIT
for _ in $(seq 1 60); do
	curl -s -o /dev/null "$BASE/healthz" && curl -s -o /dev/null "$ABASE/healthz" && break
	sleep 0.25
done
for b in "$BASE" "$ABASE"; do
	if ! curl -s -o /dev/null "$b/healthz"; then
		echo "FAIL $NAME: server did not start on $b"
		tail -20 "$OUT"/*.server.log "$OUT/server.log"
		exit 1
	fi
done

# --- STEPS ---
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
expect "create with defaults" 201 '.genre=="general" and .pages==null and .rating==0' -- -X POST -H "$JSON" -d '{"title":"Dune"}' "$BASE/books"
expect "min_length from yaml" 422 '' -- -X POST -H "$JSON" -d '{"title":""}' "$BASE/books"
expect "max_length from yaml" 422 '' -- -X POST -H "$JSON" -d "{\"title\":\"$(printf 'x%.0s' $(seq 1 41))\"}" "$BASE/books"
expect "le from yaml" 422 '' -- -X POST -H "$JSON" -d '{"title":"Bad","rating":9}' "$BASE/books"
expect "optional int" 201 '.pages==412' -- -X POST -H "$JSON" -d '{"title":"Foundation","genre":"scifi","pages":412}' "$BASE/books"
curl -s -o /dev/null -X POST -H "$JSON" -d '{"title":"Hyperion","genre":"scifi","pages":482}' "$BASE/books"
curl -s -o /dev/null -X POST -H "$JSON" -d '{"title":"Ulysses","genre":"fiction","pages":730}' "$BASE/books"
expect "defaults pagination" 200 '.count==4 and .pages==2 and (.results|length)==3' -- "$BASE/books"
expect "defaults filtering" 200 '.count==2' -- "$BASE/books?genre=scifi"
expect "defaults search" 200 '.count==1 and .results[0].title=="Ulysses"' -- "$BASE/books?search=uly"
expect "defaults ordering" 200 '.results[0].title=="Ulysses"' -- "$BASE/books?ordering=-pages"
expect "yaml get-only endpoint" 405 '.detail=="Method Not Allowed. Allowed: GET"' -- -X POST -H "$JSON" -d '{"text":"x"}' "$BASE/notes"
expect "yaml auth: no token" 401 '' -- "$BASE/secrets"
expect "yaml login validator by dotted path" 200 '(.token|type)=="string"' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
TOKEN=$(body .token)
expect "yaml auth: with token" 200 '.results==[]' -- -H "Authorization: Bearer $TOKEN" "$BASE/secrets"
expect "yaml per-method: anonymous get" 200 '' -- "$BASE/mixed"
expect "yaml per-method: anonymous post" 401 '' -- -X POST -H "$JSON" -d '{"text":"x"}' "$BASE/mixed"
expect "yaml per-method: user post" 201 '' -- -X POST -H "$JSON" -H "Authorization: Bearer $TOKEN" -d '{"text":"x"}' "$BASE/mixed"
expect "yaml per-method: user delete is 403" 403 '.detail=="Insufficient permissions"' -- -X DELETE -H "Authorization: Bearer $TOKEN" "$BASE/mixed/1"

expect "async document: healthz" 200 '.status=="ok"' -- "$ABASE/healthz"
expect "async document: create" 201 '.id==1' -- -X POST -H "$JSON" -d '{"title":"async"}' "$ABASE/asyncbooks"
expect "async document: list" 200 '(.results|length)==1' -- "$ABASE/asyncbooks"

# a key the format does not know refuses to start and names the key
LIGHTAPI_CONFIG=$E2E/configs/12_yaml_badkey.yaml LIGHTAPI_PORT=$((PORT + 2)) LIGHTAPI_HOST=127.0.0.1 \
	uv run --frozen --extra dev --directory "$ROOT" python -m lightapi serve >"$OUT/badkey.log" 2>&1
check "unknown yaml key exits non-zero" $? -ne 0
check "unknown yaml key is named" "$(grep -c 'filtering' "$OUT/badkey.log")" -ge 1

# the CLI itself
uv run --frozen --extra dev --directory "$ROOT" python -m lightapi dance >"$OUT/dance.log" 2>&1
check "unknown command exits non-zero" $? -ne 0
env -u LIGHTAPI_CONFIG uv run --frozen --extra dev --directory "$ROOT" python -m lightapi serve >"$OUT/noconfig.log" 2>&1
check "missing LIGHTAPI_CONFIG exits non-zero" $? -ne 0
check "missing LIGHTAPI_CONFIG says so" "$(grep -ci 'LIGHTAPI_CONFIG' "$OUT/noconfig.log")" -ge 1

# --- end ---
check "no traceback in the sync server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
check "no traceback in the async server log" "$(grep -c Traceback "$OUT/async.server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
