#!/usr/bin/env bash
# e2e:
# Page-number links over 25 rows, and a full cursor walk that sees each id exactly once.
set -u
NAME=07_pagination
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
postgresql*) $E2E_PSQL -q -c "DROP TABLE IF EXISTS e2e07_page_items, e2e07_cursor_items" ;;
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
for i in $(seq 1 25); do
	curl -s -o /dev/null -X POST -H "$JSON" -d "{\"label\":\"p$i\"}" "$BASE/pages"
	curl -s -o /dev/null -X POST -H "$JSON" -d "{\"label\":\"c$i\"}" "$BASE/cursor"
done
expect "page 1" 200 '.count==25 and .pages==13 and (.results|length)==2 and .previous==null and (.next|endswith("?page=2")) and .results[0].id==1' -- "$BASE/pages"
expect "page 2" 200 '(.previous|endswith("?page=1")) and (.next|endswith("?page=3")) and .results[0].id==3' -- "$BASE/pages?page=2"
expect "last page" 200 '(.results|length)==1 and .results[0].id==25 and .next==null' -- "$BASE/pages?page=13"
expect "beyond last page" 200 '.results==[] and .count==25' -- "$BASE/pages?page=99"
expect "page zero is page one" 200 '.results[0].id==1 and .previous==null' -- "$BASE/pages?page=0"
expect "page text is page one" 200 '.results[0].id==1' -- "$BASE/pages?page=abc"
expect "negative page is page one" 200 '.results[0].id==1' -- "$BASE/pages?page=-3"

expect "cursor first page" 200 '(.results|length)==2 and .results[0].id==1 and (.next|type)=="string" and .previous==null' -- "$BASE/cursor"
IDS=$(body '.results[].id')
NEXT=$(body .next)
HOPS=1
while [ "$NEXT" != null ] && [ $HOPS -lt 40 ]; do
	curl -s -o "$OUT/body" "$BASE/cursor?cursor=$NEXT"
	IDS="$IDS $(body '.results[].id')"
	NEXT=$(body .next)
	HOPS=$((HOPS + 1))
done
check "cursor walk takes 13 pages" $HOPS -eq 13
check "cursor walk sees 25 rows" "$(echo $IDS | wc -w | tr -d ' ')" -eq 25
check "cursor walk sees each id once" "$(echo $IDS | tr ' ' '\n' | sort -n | uniq | wc -l | tr -d ' ')" -eq 25
check "cursor walk is ordered" "$(echo $IDS | tr ' ' '\n' | tail -1)" -eq 25
expect "invalid cursor is first page" 200 '.results[0].id==1' -- "$BASE/cursor?cursor=not-a-cursor"
expect "cursor past the end" 200 '.results==[] and .next==null' -- "$BASE/cursor?cursor=$(printf '{"id":25}' | base64)"
expect "cursor detail route unaffected" 200 '.id==7' -- "$BASE/cursor/7"

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
