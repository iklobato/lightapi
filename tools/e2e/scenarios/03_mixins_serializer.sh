#!/usr/bin/env bash
# e2e:
# HttpMethod mixins answer 405 with Allow; the four Serializer forms project fields.
set -u
NAME=03_mixins_serializer
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
postgresql*) $E2E_PSQL -q -c "DROP TABLE IF EXISTS e2e03_notes, e2e03_events, e2e03_users, e2e03_orders, e2e03_alpha, e2e03_beta, e2e03_inbox_read, e2e03_inbox_write" ;;
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
expect "get-only: list" 200 '.results==[]' -- "$BASE/notes"
expect "get-only: post is 405" 405 '.detail=="Method Not Allowed. Allowed: GET"' -- -X POST -H "$JSON" -d '{"text":"x"}' "$BASE/notes"
header "get-only: allow header" '^allow: GET'
expect "get-only: put is 405" 405 '.detail=="Method Not Allowed. Allowed: GET"' -- -X PUT -H "$JSON" -d '{"text":"x","version":1}' "$BASE/notes/1"
expect "get-only: delete is 405" 405 '' -- -X DELETE "$BASE/notes/1"
expect "get+post: post" 201 '.name=="launch"' -- -X POST -H "$JSON" -d '{"name":"launch"}' "$BASE/events"
expect "get+post: put is 405" 405 '.detail=="Method Not Allowed. Allowed: GET"' -- -X PUT -H "$JSON" -d '{"name":"x","version":1}' "$BASE/events/1"
expect "get+post: patch is 405" 405 '' -- -X PATCH -H "$JSON" -d '{"name":"x","version":1}' "$BASE/events/1"
expect "get+post: get detail" 200 '.id==1' -- "$BASE/events/1"
expect "same path, two classes: get goes to the reader" 200 '.results==[]' -- "$BASE/inbox"
expect "same path, two classes: post goes to the writer" 201 '.text=="hi"' -- -X POST -H "$JSON" -d '{"text":"hi"}' "$BASE/inbox"
expect "same path, two classes: reader list is still empty" 200 '.results==[]' -- "$BASE/inbox"
expect "fields=: post hides secret" 201 '(keys|sort)==["email","id","name"]' -- -X POST -H "$JSON" -d '{"name":"ana","email":"a@x","secret":"hunter2"}' "$BASE/users"
expect "fields=: get hides secret" 200 '(.results[0]|keys|sort)==["email","id","name"]' -- "$BASE/users"
expect "read/write: post shows write fields" 201 '(keys|sort)==["id","name"]' -- -X POST -H "$JSON" -d '{"name":"o1","tag":"vip"}' "$BASE/orders"
expect "read/write: get shows read fields" 200 '(keys|sort)==["id","name","tag"] and .tag=="vip"' -- "$BASE/orders/1"
expect "read/write: list shows read fields" 200 '(.results[0]|keys|sort)==["id","name","tag"]' -- "$BASE/orders"
expect "subclass: alpha post" 201 '(keys|sort)==["id","name"]' -- -X POST -H "$JSON" -d '{"name":"a","extra":"hidden"}' "$BASE/alpha"
expect "subclass: beta post" 201 '(keys|sort)==["id","name"]' -- -X POST -H "$JSON" -d '{"name":"b","extra":"hidden"}' "$BASE/beta"
expect "subclass: alpha get" 200 '(keys|sort)==["id","name"]' -- "$BASE/alpha/1"
expect "subclass: beta get" 200 '(keys|sort)==["id","name"]' -- "$BASE/beta/1"

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
