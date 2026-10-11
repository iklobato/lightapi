#!/usr/bin/env bash
# e2e: async
# Middleware order (pre in declaration order, post reversed), short-circuit, CORS headers.
set -u
NAME=09_middleware
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
E2E=$ROOT/tools/e2e
OUT=$E2E/.out/$NAME
mkdir -p "$OUT"
PORT=${E2E_PORT:-18100}
BASE=http://127.0.0.1:$PORT
DB_URL=${E2E_DB_URL:-sqlite+aiosqlite:///$OUT/db.sqlite}
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
postgresql*) $E2E_PSQL -q -c "DROP TABLE IF EXISTS e2e09_items" ;;
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
expect "post through the chain" 201 '.name=="a"' -- -X POST -H "$JSON" -d '{"name":"a"}' "$BASE/items"
header "post-hook header" '^x-e2e-stamp: yes'
expect "get through the chain" 200 '(.results|length)==1' -- "$BASE/items"
header "post-hook header on get" '^x-e2e-stamp: yes'
sleep 0.2
check "pre hooks run in declaration order" "$(grep -E '^hook pre:' "$OUT/server.log" | head -2 | tr '\n' ' ')" = "hook pre:stamp hook pre:trace "
check "post hooks run last registered first" "$(grep -E '^hook post:' "$OUT/server.log" | head -2 | tr '\n' ' ')" = "hook post:trace hook post:stamp "
expect "short-circuit answers before the endpoint" 418 '.detail=="teapot"' -- -X POST -H "$JSON" -H 'x-teapot: 1' -d '{"name":"never"}' "$BASE/items"
expect "short-circuit wrote nothing" 200 '(.results|length)==1' -- "$BASE/items"
expect "cors header for an allowed origin" 200 '' -- -H 'Origin: http://e2e.local' "$BASE/items"
header "access-control-allow-origin" '^access-control-allow-origin: http://e2e.local'
expect "cors preflight" 200 '' -- -X OPTIONS -H 'Origin: http://e2e.local' -H 'Access-Control-Request-Method: POST' "$BASE/items"
header "preflight allows POST" '^access-control-allow-methods: .*POST'
expect "cors unknown origin gets no header" 200 '' -- -H 'Origin: http://evil.local' "$BASE/items"
check "no allow-origin for unknown origin" "$(grep -ci '^access-control-allow-origin' "$OUT/headers")" -eq 0

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
