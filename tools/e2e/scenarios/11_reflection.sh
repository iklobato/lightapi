#!/usr/bin/env bash
# e2e: pg
# Full and partial reflection of tables created by SQL first; a missing table refuses to start.
set -u
NAME=11_reflection
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

# --- pre-start: the tables exist and are seeded before the server starts ---
case $DB_URL in
sqlite*)
	rm -f "$OUT/db.sqlite"
	sqlite3 "$OUT/db.sqlite" <<'SQL'
CREATE TABLE e2e11_products (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT NOT NULL, name TEXT NOT NULL,
  price NUMERIC(10, 2) NOT NULL, created_at TIMESTAMP, updated_at TIMESTAMP, version INTEGER NOT NULL DEFAULT 1);
INSERT INTO e2e11_products (sku, name, price) VALUES ('A-1', 'Anvil', 12.50), ('B-2', 'Bolt', 0.25);
CREATE TABLE e2e11_docs (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, notes TEXT,
  created_at TIMESTAMP, updated_at TIMESTAMP, version INTEGER NOT NULL DEFAULT 1);
SQL
	;;
postgresql*)
	$E2E_PSQL -q <<'SQL'
DROP TABLE IF EXISTS e2e11_products; DROP TABLE IF EXISTS e2e11_docs; DROP TABLE IF EXISTS e2e11_ghost;
CREATE TABLE e2e11_products (id SERIAL PRIMARY KEY, sku TEXT NOT NULL, name TEXT NOT NULL,
  price NUMERIC(10, 2) NOT NULL, created_at TIMESTAMP, updated_at TIMESTAMP, version INTEGER NOT NULL DEFAULT 1);
INSERT INTO e2e11_products (sku, name, price) VALUES ('A-1', 'Anvil', 12.50), ('B-2', 'Bolt', 0.25);
CREATE TABLE e2e11_docs (id SERIAL PRIMARY KEY, title TEXT NOT NULL, notes TEXT,
  created_at TIMESTAMP, updated_at TIMESTAMP, version INTEGER NOT NULL DEFAULT 1);
SQL
	;;
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
expect "full: seeded rows are listed" 200 '(.results|length)==2 and .results[0].sku=="A-1" and .results[0].price=="12.50"' -- "$BASE/products"
expect "full: numeric is a json string" 200 '(.price|type)=="string"' -- "$BASE/products/1"
expect "full: post" 201 '.id==3 and .sku=="C-3" and .version==1 and (.created_at|type)=="string"' -- -X POST -H "$JSON" -d '{"sku":"C-3","name":"Cog","price":"3.75"}' "$BASE/products"
expect "full: put" 200 '.version==2 and .name=="Cogwheel"' -- -X PUT -H "$JSON" -d '{"sku":"C-3","name":"Cogwheel","price":"3.75","version":1}' "$BASE/products/3"
expect "full: patch" 200 '.version==3 and .price=="4.00"' -- -X PATCH -H "$JSON" -d '{"price":"4.00","version":2}' "$BASE/products/3"
expect "reflected patch without version" 422 '(.detail|type)=="array"' -- -X PATCH -H "$JSON" -d '{"price":"5.00"}' "$BASE/products/3"
expect "full: stale version" 409 '.detail=="version conflict"' -- -X PATCH -H "$JSON" -d '{"price":"5.00","version":1}' "$BASE/products/3"
expect "full: missing required column" 422 '' -- -X POST -H "$JSON" -d '{"sku":"D-4"}' "$BASE/products"
expect "full: delete" 204 '' -- -X DELETE "$BASE/products/3"
expect "partial: post with the declared column" 201 '.title=="Doc1" and .notes=="my notes"' -- -X POST -H "$JSON" -d '{"title":"Doc1","notes":"my notes"}' "$BASE/docs"
expect "partial: declared default applies" 201 '.notes==""' -- -X POST -H "$JSON" -d '{"title":"Doc2"}' "$BASE/docs"
expect "partial: list shows both columns" 200 '(.results|length)==2 and (.results[0]|has("notes")) and (.results[0]|has("title"))' -- "$BASE/docs"
expect "partial: reflected column is validated" 422 '' -- -X POST -H "$JSON" -d '{"notes":"no title"}' "$BASE/docs"

# a reflected table that does not exist refuses to start
MISSING_LOG=$OUT/missing.server.log
E2E_PORT=$((PORT + 1)) E2E_DB_URL=$DB_URL E2E_OUT=$OUT PYTHONPATH=$E2E \
	uv run --frozen --extra dev --extra async --directory "$ROOT" python "$E2E/apps/11_reflection_missing.py" >"$MISSING_LOG" 2>&1
check "missing table: process exits non-zero" $? -ne 0
check "missing table: ConfigurationError in the log" "$(grep -c 'ConfigurationError' "$MISSING_LOG")" -ge 1
check "missing table: the message names the table" "$(grep -c 'e2e11_ghost' "$MISSING_LOG")" -ge 1

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
