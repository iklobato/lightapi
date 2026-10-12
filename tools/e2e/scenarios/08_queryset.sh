#!/usr/bin/env bash
# e2e: async
# Static, sync and async queryset hooks filter the list route; retrieve ignores them (pinned).
set -u
NAME=08_queryset
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
postgresql*) $E2E_PSQL -q -c "DROP TABLE IF EXISTS e2e08_static, e2e08_sync, e2e08_async" ;;
esac

# --- start the server ---
E2E_PORT=$PORT E2E_DB_URL=$DB_URL E2E_OUT=$OUT LIGHTAPI_JWT_SECRET=e2e-secret PYTHONPATH=$E2E \
	uv run --frozen --extra dev --extra async --directory "$ROOT" python "$E2E/apps/$NAME.py" >"$OUT/server.log" 2>&1 &
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
for route in static sync async; do
	curl -s -o /dev/null -X POST -H "$JSON" -d '{"title":"draft","published":false}' "$BASE/$route"
	curl -s -o /dev/null -X POST -H "$JSON" -d '{"title":"live one","published":true,"words":100}' "$BASE/$route"
	curl -s -o /dev/null -X POST -H "$JSON" -d '{"title":"live two","published":true,"words":900}' "$BASE/$route"
done
expect "static: list shows published only" 200 '(.results|length)==2 and all(.results[]; .published==true)' -- "$BASE/static"
expect "sync: list shows published only" 200 '(.results|length)==2 and all(.results[]; .published==true)' -- "$BASE/sync"
expect "async: list shows published only" 200 '(.results|length)==2' -- "$BASE/async"
expect "async: query parameter reaches the hook" 200 '(.results|length)==1 and .results[0].words==900' -- "$BASE/async?min_words=500"
expect "async: hook that excludes all" 200 '.results==[]' -- "$BASE/async?min_words=5000"
expect "static: retrieve ignores the queryset" 200 '.id==1 and .published==false' -- "$BASE/static/1"
expect "sync: retrieve ignores the queryset" 200 '.id==1 and .published==false' -- "$BASE/sync/1"
expect "async: retrieve ignores the queryset" 200 '.id==1 and .published==false' -- "$BASE/async/1"
expect "async: post still works" 201 '.id==4' -- -X POST -H "$JSON" -d '{"title":"new","published":true}' "$BASE/async"
expect "async: patch a filtered-out row" 200 '.version==2' -- -X PATCH -H "$JSON" -d '{"title":"draft2","version":1}' "$BASE/async/1"

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
