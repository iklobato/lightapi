#!/usr/bin/env bash
# e2e: docker
# The container image built from this checkout serves the mounted YAML, reports healthy and runs as uid 1001.
set -u
NAME=16_docker
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
E2E=$ROOT/tools/e2e
OUT=$E2E/.out/$NAME
mkdir -p "$OUT"
PORT=${E2E_PORT:-18199}
BASE=http://127.0.0.1:$PORT
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

# --- build the wheel from this checkout and the image from it ---
# The build context holds only dist/ and docker/: the repository .dockerignore excludes dist.
IMAGE=lightapi-e2e
CONTAINER=lightapi-e2e-app
rm -rf "$OUT/ctx"
mkdir -p "$OUT/ctx/dist" "$OUT/ctx/docker"
# Built into the scenario's own directory: the repository dist/ may hold a release build.
(cd "$ROOT" && uv build --out-dir "$OUT/ctx/dist" >"$OUT/build.log" 2>&1) || {
	echo "FAIL $NAME: uv build failed"
	tail -20 "$OUT/build.log"
	exit 1
}
rm -f "$OUT"/ctx/dist/*.tar.gz
cp "$ROOT/docker/entrypoint.py" "$OUT/ctx/docker/"
docker build -q -t $IMAGE -f "$E2E/Dockerfile.local" "$OUT/ctx" >"$OUT/docker-build.log" 2>&1 || {
	echo "FAIL $NAME: docker build failed"
	tail -30 "$OUT/docker-build.log"
	exit 1
}
docker rm -f $CONTAINER >/dev/null 2>&1 || true
docker run -d --rm --name $CONTAINER -p 127.0.0.1:"$PORT":8000 \
	-v "$E2E/configs/16_docker.yaml:/app/lightapi.yaml:ro" $IMAGE >/dev/null
trap 'docker rm -f $CONTAINER >/dev/null 2>&1' EXIT
for _ in $(seq 1 60); do
	curl -s -o /dev/null "$BASE/healthz" && break
	sleep 0.5
done
if ! curl -s -o /dev/null "$BASE/healthz"; then
	echo "FAIL $NAME: container did not answer"
	docker logs $CONTAINER 2>&1 | tail -20
	exit 1
fi

# --- STEPS ---
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
expect "create" 201 '.id==1' -- -X POST -H "$JSON" -d '{"title":"in a container"}' "$BASE/books"
expect "list" 200 '(.results|length)==1' -- "$BASE/books"
expect "validation" 422 '' -- -X POST -H "$JSON" -d '{"title":""}' "$BASE/books"
for _ in $(seq 1 20); do
	[ "$(docker inspect -f '{{.State.Health.Status}}' $CONTAINER)" = healthy ] && break
	sleep 1
done
check "docker reports healthy" "$(docker inspect -f '{{.State.Health.Status}}' $CONTAINER)" = healthy
check "runs as the non-root user" "$(docker exec $CONTAINER id -u)" = 1001

# --- end ---
docker logs $CONTAINER >"$OUT/server.log" 2>&1
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
