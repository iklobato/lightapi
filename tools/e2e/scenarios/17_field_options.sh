#!/usr/bin/env bash
# e2e: pg
# Field column options (unique, index, foreign_key, exclude, decimal_places) reach the schema; a duplicate unique value is 409.
set -u
NAME=17_field_options
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
postgresql*) $E2E_PSQL -q -c "DROP TABLE IF EXISTS e2e17_products; DROP TABLE IF EXISTS e2e17_categories" ;;
esac

# --- start the server ---
E2E_PORT=$PORT E2E_DB_URL=$DB_URL E2E_OUT=$OUT PYTHONPATH=$E2E \
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
case $DB_URL in
sqlite*) SCHEMA=$(sqlite3 "$OUT/db.sqlite" '.schema e2e17_products' '.indexes e2e17_products') ;;
postgresql*) SCHEMA=$($E2E_PSQL -c '\d e2e17_products') ;;
esac
check "unique constraint in the schema" "$(printf '%s' "$SCHEMA" | grep -ciE 'unique')" -ge 1
check "index in the schema" "$(printf '%s' "$SCHEMA" | grep -ciE 'ix_e2e17_products_name')" -ge 1
check "foreign key in the schema" "$(printf '%s' "$SCHEMA" | grep -ciE 'e2e17_categories')" -ge 1
check "excluded field is not a column" "$(printf '%s' "$SCHEMA" | grep -ci 'internal_note')" -eq 0
expect "create category" 201 '.id==1' -- -X POST -H "$JSON" -d '{"name":"tools"}' "$BASE/categories"
expect "create product" 201 '.sku=="A-1" and (.price|type)=="string" and (.price|tonumber)==12.5 and .category_id==1 and (has("internal_note")|not)' \
	-- -X POST -H "$JSON" -d '{"sku":"A-1","name":"Anvil","price":"12.50","category_id":1,"internal_note":"ignored"}' "$BASE/products"
expect "duplicate sku is 409" 409 '.detail=="constraint violation"' -- -X POST -H "$JSON" -d '{"sku":"A-1","name":"Again","price":"1.00"}' "$BASE/products"
expect "table still has one row" 200 '(.results|length)==1' -- "$BASE/products"
# ids come from the responses: on Postgres the refused INSERT still consumed a sequence value
expect "second product" 201 '.sku=="B-2"' -- -X POST -H "$JSON" -d '{"sku":"B-2","name":"Bolt","price":"0.25"}' "$BASE/products"
SECOND=$(body .id)
expect "put to duplicate sku" 409 '.detail=="constraint violation"' -- -X PUT -H "$JSON" -d '{"sku":"A-1","name":"Bolt","price":"0.25","version":1}' "$BASE/products/$SECOND"
expect "row untouched after the 409" 200 '.sku=="B-2" and .version==1' -- "$BASE/products/$SECOND"
expect "writes still work after the 409" 201 '.sku=="C-3"' -- -X POST -H "$JSON" -d '{"sku":"C-3","name":"Cog","price":"3.75"}' "$BASE/products"
expect "more decimal places than declared is 422" 422 '.detail[0].loc==["price"]' -- -X POST -H "$JSON" -d '{"sku":"D-4","name":"Dial","price":"1.999"}' "$BASE/products"
expect "declared decimal places are kept" 201 '.price=="1.99"' -- -X POST -H "$JSON" -d '{"sku":"D-4","name":"Dial","price":"1.99"}' "$BASE/products"

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
