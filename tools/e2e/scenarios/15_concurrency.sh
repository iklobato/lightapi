#!/usr/bin/env bash
# e2e: pg-only
# Ten parallel writers on Postgres: one PUT wins with 200, nine see 409, the version advances once.
set -u
NAME=15_concurrency
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
E2E=$ROOT/tools/e2e
OUT=$E2E/.out/$NAME
mkdir -p "$OUT"
PORT=${E2E_PORT:-18100}
BASE=http://127.0.0.1:$PORT
DB_URL=${E2E_DB_URL:-sqlite:///$OUT/db.sqlite}
case $DB_URL in postgresql*) ;; *) echo "== $NAME: 0 passed, 0 failed (needs E2E_DB_URL=postgresql+psycopg2://..., skipped)"; exit 0 ;; esac
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
postgresql*) $E2E_PSQL -q -c "DROP TABLE IF EXISTS e2e15_counters" ;;
esac

# --- start the server ---
E2E_PORT=$PORT E2E_DB_URL=$DB_URL E2E_OUT=$OUT PYTHONPATH=$E2E \
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
expect "create" 201 '.version==1' -- -X POST -H "$JSON" -d '{"label":"c","hits":0}' "$BASE/counters"
: >"$OUT/codes"
seq 1 10 | xargs -P 10 -I{} curl -s -o /dev/null -w '%{http_code}\n' -X PUT -H "$JSON" -d '{"label":"c","hits":{},"version":1}' "$BASE/counters/1" >>"$OUT/codes"
check "exactly one writer wins" "$(grep -c '^200$' "$OUT/codes")" -eq 1
check "the other nine see the conflict" "$(grep -c '^409$' "$OUT/codes")" -eq 9
check "no other status" "$(wc -l <"$OUT/codes" | tr -d ' ')" -eq 10
expect "version advanced once" 200 '.version==2' -- "$BASE/counters/1"
: >"$OUT/codes2"
seq 1 10 | xargs -P 10 -I{} curl -s -o /dev/null -w '%{http_code}\n' -X PATCH -H "$JSON" -d '{"hits":{},"version":2}' "$BASE/counters/1" >>"$OUT/codes2"
check "patch: exactly one writer wins" "$(grep -c '^200$' "$OUT/codes2")" -eq 1
expect "version advanced once more" 200 '.version==3' -- "$BASE/counters/1"

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
