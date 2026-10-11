#!/usr/bin/env bash
# e2e:
# Meta.cache with Redis unreachable: every request is served from the database and each miss is logged.
set -u
NAME=14_cache_fallback
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
postgresql*) $E2E_PSQL -q -c "DROP TABLE IF EXISTS e2e14_reports" ;;
esac

# --- start the server ---
E2E_PORT=$PORT E2E_DB_URL=$DB_URL E2E_OUT=$OUT LIGHTAPI_REDIS_URL=redis://127.0.0.1:1/0 PYTHONPATH=$E2E \
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
check "startup warns that redis is unreachable" "$(grep -c 'not reachable at startup' "$OUT/server.log")" -ge 1
expect "get served from the database" 200 '.results==[]' -- "$BASE/reports"
expect "post" 201 '.id==1' -- -X POST -H "$JSON" -d '{"title":"q1"}' "$BASE/reports"
expect "get sees the new row (no stale cache)" 200 '(.results|length)==1' -- "$BASE/reports"
expect "get detail" 200 '.id==1' -- "$BASE/reports/1"
expect "delete" 204 '' -- -X DELETE "$BASE/reports/1"
expect "get after delete" 200 '.results==[]' -- "$BASE/reports"

# --- end: the only tracebacks allowed are the ones each Redis fallback logs ---
check "cache misses are logged" "$(grep -cE 'Cache read failed' "$OUT/server.log")" -ge 1
# redis chains ConnectionRefusedError into its ConnectionError, so one fallback prints two
# Traceback headers: a header is stray only when the line before it is neither a fallback
# message nor the chaining line.
STRAY=$(awk '/^Traceback \(most recent call last\):/ { if (prev !~ /Cache (read|write|invalidation) failed|Redis is not reachable|During handling of the above exception|direct cause of the following exception/) n++ } NF { prev = $0 } END { print n + 0 }' "$OUT/server.log")
check "every traceback belongs to a redis fallback" "$STRAY" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
