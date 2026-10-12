#!/usr/bin/env bash
# e2e: pg
# Field, search and ordering filters combined with page pagination; literal % and _ in search.
set -u
NAME=06_filtering
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
postgresql*) $E2E_PSQL -q -c "DROP TABLE IF EXISTS e2e06_books" ;;
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
seed() { curl -s -o /dev/null -X POST -H "$JSON" -d "$1" "$BASE/books"; }
seed '{"title":"Python Basics","genre":"tech","price":30.0,"pages":100,"published":true}'
seed '{"title":"python advanced","genre":"tech","price":45.5,"pages":300,"published":true}'
seed '{"title":"Rust in Action","genre":"tech","price":40.0,"pages":250,"published":false}'
seed '{"title":"100% Pure","genre":"fiction","price":12.0,"pages":200,"published":true}'
seed '{"title":"under_score","genre":"fiction","price":15.0,"pages":100,"published":true}'
seed '{"title":"Dune","genre":"scifi","price":20.0,"pages":600,"published":true}'
seed '{"title":"Foundation","genre":"scifi","price":18.0,"pages":255,"published":true}'
seed '{"title":"Hyperion","genre":"scifi","price":22.0,"pages":480,"published":false}'
seed '{"title":"Neuromancer","genre":"scifi","price":16.0,"pages":270,"published":true}'
seed '{"title":"Snow Crash","genre":"scifi","price":17.0,"pages":440,"published":true}'
seed '{"title":"Pythonic Thinking","genre":"scifi","price":9.0,"pages":100,"published":true}'
seed '{"title":"Ulysses","genre":"fiction","price":11.0,"pages":730,"published":true}'
expect "all seeded" 200 '.count==12 and .pages==3' -- "$BASE/books"
expect "filter genre" 200 '.count==6 and all(.results[]; .genre=="scifi")' -- "$BASE/books?genre=scifi"
expect "filter bool coerced" 200 '.count==2 and all(.results[]; .published==false)' -- "$BASE/books?published=false"
expect "filter int coerced" 200 '.count==3 and all(.results[]; .pages==100)' -- "$BASE/books?pages=100"
expect "filter int garbage is 422" 422 '.detail[0].loc==["query","pages"]' -- "$BASE/books?pages=lots"
expect "filter int with a fraction is 422" 422 '.detail[0].loc==["query","pages"]' -- "$BASE/books?pages=1.5"
expect "filter float garbage is 422" 422 '.detail[0].loc==["query","price"]' -- "$BASE/books?price=cheap"
expect "filter int beyond 64 bits is 422" 422 '.detail[0].loc==["query","pages"]' -- "$BASE/books?pages=99999999999999999999"
expect "search case-insensitive" 200 '.count==3' -- "$BASE/books?search=python"
expect "search percent literal" 200 '.count==1 and .results[0].title=="100% Pure"' -- "$BASE/books?search=%25"
expect "search underscore literal" 200 '.count==1 and .results[0].title=="under_score"' -- "$BASE/books?search=_"
expect "search no match" 200 '.count==0 and .results==[]' -- "$BASE/books?search=zzzz"
expect "ordering desc" 200 '.results[0].price==45.5 and .results[1].price==40.0' -- "$BASE/books?ordering=-price"
expect "ordering asc" 200 '.results[0].price==9.0' -- "$BASE/books?ordering=price"
expect "ordering field not allowed is ignored" 200 '.count==12 and .results[0].id==1' -- "$BASE/books?ordering=title"
expect "filter field not allowed is ignored" 200 '.count==12' -- "$BASE/books?title=Dune"
expect "filter + search + order" 200 '.count==1 and .results[0].title=="Pythonic Thinking"' -- "$BASE/books?genre=scifi&search=python&ordering=price"
expect "filter + order + page 1" 200 '.count==6 and (.results|length)==5 and .results[0].price==9.0 and (.next|contains("genre=scifi")) and (.next|contains("ordering=price"))' -- "$BASE/books?genre=scifi&ordering=price&page=1"
expect "filter + order + page 2" 200 '(.results|length)==1 and .results[0].price==22.0 and .next==null and (.previous|contains("page=1"))' -- "$BASE/books?genre=scifi&ordering=price&page=2"

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
