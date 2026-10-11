#!/usr/bin/env bash
# Runs every tools/e2e/scenarios/*.sh: SQLite first, then again on a throwaway Postgres
# for the scenarios tagged `pg`. Exit 0 only when every run passed.
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
E2E=$ROOT/tools/e2e
OUT=$E2E/.out
mkdir -p "$OUT"
FILTER=${1:-}

for tool in jq curl uv sqlite3 psql; do
	command -v "$tool" >/dev/null || {
		echo "missing tool: $tool"
		exit 1
	}
done

# The [pg] runs need both Postgres drivers in the interpreter the scripts use. asyncpg comes
# from the `async` extra; psycopg2 is not in the manifest, so it must be installed by hand
# (`uv pip install psycopg2-binary`). This first `uv run` also builds a fresh environment
# (UV_PYTHON=3.10 ...) before any server has to answer within its start window.
if [ "${E2E_NO_DOCKER:-}" != 1 ]; then
	uv run --frozen --extra dev --extra async --directory "$ROOT" python -c "import asyncpg, psycopg2" >"$OUT/drivers.log" 2>&1 || {
		echo "the [pg] runs need asyncpg and psycopg2 in the uv environment:"
		tail -1 "$OUT/drivers.log"
		echo "install with: uv pip install psycopg2-binary   (E2E_NO_DOCKER=1 skips the [pg] runs)"
		exit 1
	}
fi

HAVE_DOCKER=0
command -v docker >/dev/null && docker info >/dev/null 2>&1 && HAVE_DOCKER=1
PG_NAME=lightapi-e2e-pg
PG_PORT=55432
PG_PASSWORD=e2e # a throwaway container on loopback; kept out of the URLs so scanners stay quiet
PG_READY=0
if [ $HAVE_DOCKER = 1 ]; then
	docker rm -f $PG_NAME >/dev/null 2>&1 || true
	docker run -d --rm --name $PG_NAME -e POSTGRES_PASSWORD="$PG_PASSWORD" -p 127.0.0.1:$PG_PORT:5432 postgres:16 >/dev/null
	trap 'docker rm -f $PG_NAME >/dev/null 2>&1' EXIT
	export E2E_PG_URL=postgresql+psycopg2://postgres:$PG_PASSWORD@127.0.0.1:$PG_PORT/postgres
	export E2E_PG_ASYNC_URL=postgresql+asyncpg://postgres:$PG_PASSWORD@127.0.0.1:$PG_PORT/postgres
	export E2E_PSQL="psql postgresql://postgres:$PG_PASSWORD@127.0.0.1:$PG_PORT/postgres"
	# pg_isready answers before initdb's restart; a real query from the host is the proof.
	for _ in $(seq 1 60); do
		$E2E_PSQL -qAt -c 'select 1' >/dev/null 2>&1 && PG_READY=1 && break
		sleep 0.5
	done
	[ $PG_READY = 1 ] || echo "postgres container did not become ready; [pg] runs will fail"
fi

port=18100
ok=0
fail=0
skipped=0

port_is_free() { ! lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

run_one() { # run_one <label> <script> [VAR=value ...]
	local label=$1 script=$2
	shift 2
	local tries=0
	until port_is_free "$port" || [ $tries -ge 5 ]; do
		port=$((port + 1))
		tries=$((tries + 1))
	done
	local log=$OUT/$label.log
	local status
	if env E2E_PORT=$port "$@" bash "$script" >"$log" 2>&1; then
		status=ok
		ok=$((ok + 1))
	else
		status=FAIL
		fail=$((fail + 1))
	fi
	local summary
	summary=$(grep -E '^== ' "$log" | tail -1 | sed 's/^== [^:]*: //')
	printf '%-5s %-26s %s\n' "$status" "$label" "${summary:-no summary, see $log}"
	[ "$status" = FAIL ] && grep -E '^FAIL' "$log" | head -5 | sed 's/^/      /'
	port=$((port + 1))
}

for script in "$E2E"/scenarios/[0-9]*.sh; do
	name=$(basename "$script" .sh)
	if [ -n "$FILTER" ] && [[ $name != *$FILTER* ]]; then continue; fi
	tags=$(sed -n '2p' "$script")
	case $tags in
	*docker*)
		if [ "${E2E_DOCKER:-0}" != 1 ]; then
			printf 'SKIP  %-26s set E2E_DOCKER=1 to run\n' "$name"
			skipped=$((skipped + 1))
			continue
		fi
		;;
	esac
	case $tags in
	*pg-only*) ;;
	*) run_one "$name" "$script" ;;
	esac
	case $tags in
	*pg*)
		if [ $HAVE_DOCKER = 1 ]; then
			case $tags in *async*) url=$E2E_PG_ASYNC_URL ;; *) url=$E2E_PG_URL ;; esac
			run_one "${name}[pg]" "$script" E2E_DB_URL="$url"
		elif [ "${E2E_NO_DOCKER:-0}" = 1 ]; then
			printf 'SKIP  %-26s no docker\n' "${name}[pg]"
			skipped=$((skipped + 1))
		else
			printf 'FAIL  %-26s docker is required for [pg] runs (E2E_NO_DOCKER=1 to skip)\n' "${name}[pg]"
			fail=$((fail + 1))
		fi
		;;
	esac
done

echo
echo "$ok ok, $fail failed, $skipped skipped. Logs in $OUT/"
exit $((fail > 0))
