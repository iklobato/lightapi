#!/usr/bin/env bash
# e2e: pg
# CRUD, auto columns, optimistic locking and the documented 404/409/422 replies.
set -u
NAME=01_crud_sync
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
postgresql*) $E2E_PSQL -q -c "DROP TABLE IF EXISTS e2e01_books" ;;
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
expect "list empty" 200 '.results==[]' -- "$BASE/books"
expect "create" 201 '.id==1 and .version==1 and .title=="Clean Code" and .pages==null and (.created_at|type)=="string" and (.updated_at|type)=="string"' \
	-- -X POST -H "$JSON" -d '{"title":"Clean Code","author":"Martin"}' "$BASE/books"
ID=$(body .id)
expect "list has one" 200 '(.results|length)==1 and .results[0].id==1' -- "$BASE/books"
expect "get" 200 ".id==$ID and .author==\"Martin\"" -- "$BASE/books/$ID"
expect "put" 200 '.version==2 and .pages==464 and .author=="Robert C. Martin"' \
	-- -X PUT -H "$JSON" -d '{"title":"Clean Code","author":"Robert C. Martin","pages":464,"version":1}' "$BASE/books/$ID"
expect "patch keeps the other fields" 200 '.version==3 and .pages==500 and .author=="Robert C. Martin"' \
	-- -X PATCH -H "$JSON" -d '{"pages":500,"version":2}' "$BASE/books/$ID"
expect "put stale version" 409 '.detail=="version conflict"' \
	-- -X PUT -H "$JSON" -d '{"title":"x","author":"y","version":1}' "$BASE/books/$ID"
expect "patch stale version" 409 '.detail=="version conflict"' \
	-- -X PATCH -H "$JSON" -d '{"pages":1,"version":1}' "$BASE/books/$ID"
expect "patch without version" 422 '(.detail|type)=="array" and .detail[0].loc[0]=="version"' \
	-- -X PATCH -H "$JSON" -d '{"pages":1}' "$BASE/books/$ID"
expect "version as string accepted" 200 '.version==4 and .pages==501' \
	-- -X PATCH -H "$JSON" -d '{"pages":501,"version":"3"}' "$BASE/books/$ID"
expect "version as text rejected" 422 '(.detail|type)=="array"' \
	-- -X PATCH -H "$JSON" -d '{"pages":1,"version":"three"}' "$BASE/books/$ID"
expect "patch null clears nullable" 200 '.version==5 and .pages==null' \
	-- -X PATCH -H "$JSON" -d '{"pages":null,"version":4}' "$BASE/books/$ID"
expect "wrong type" 422 '(.detail|type)=="array"' \
	-- -X POST -H "$JSON" -d '{"title":"x","author":"y","pages":"many"}' "$BASE/books"
expect "missing required" 422 '(.detail|type)=="array"' -- -X POST -H "$JSON" -d '{"author":"nobody"}' "$BASE/books"
expect "empty string rejected" 422 '' -- -X POST -H "$JSON" -d '{"title":"","author":"x"}' "$BASE/books"
expect "invalid json" 422 '' -- -X POST -H "$JSON" -d '{not json' "$BASE/books"
expect "get missing" 404 '.detail=="not found"' -- "$BASE/books/999"
expect "put missing" 404 '.detail=="not found"' \
	-- -X PUT -H "$JSON" -d '{"title":"a","author":"b","version":1}' "$BASE/books/999"
expect "delete missing" 404 '.detail=="not found"' -- -X DELETE "$BASE/books/999"
expect "huge pk is 404 not 500" 404 '.detail=="not found"' -- "$BASE/books/99999999999999999999"
expect "delete" 204 '' -- -X DELETE "$BASE/books/$ID"
expect "get after delete" 404 '' -- "$BASE/books/$ID"
expect "delete again" 404 '' -- -X DELETE "$BASE/books/$ID"
expect "unknown route" 404 '' -- "$BASE/nope"

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
