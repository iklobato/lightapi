# End-to-end curl suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `tools/e2e/run_all.sh` serves every documented LightAPI feature as a real process, drives it with `curl` against SQLite files and a throwaway Postgres container, and exits 0 only when every expectation holds.

**Architecture:** One self-contained bash script per scenario (`tools/e2e/scenarios/NN_<name>.sh`) starts the app in `tools/e2e/apps/<name>.py` (or `python -m lightapi serve` on a YAML in `tools/e2e/configs/`), polls `/healthz`, runs `expect` steps with `curl` and `jq`, and kills the server on exit. `run_all.sh` only orchestrates: pre-checks, the Postgres container, one port per run, the `[pg]` reruns, the summary. Four library/doc fixes land in their own commits right before the scenario that proves them.

**Tech Stack:** bash, curl, jq, sqlite3, psql, docker (postgres:16), uv, the LightAPI dev extras already in `uv.lock` (aiosqlite, asyncpg, psycopg2-binary, uvicorn).

**Spec:** `docs/superpowers/specs/2026-10-11-e2e-curl-suite-design.md`

## Global Constraints

- Branch `test/e2e-curl` (on `audit/second-pass`). Never push, never publish, never change the version.
- Python 3.10 syntax only in `lightapi/` and `tools/e2e/apps/`; the suite must pass on the local 3.13 venv and under `uv run --isolated --frozen --python 3.10 --extra dev`.
- No new dependencies. No shared helper file under `tools/e2e/`: every scenario script carries its own `expect`, `header`, `check` functions (the project rule against wrapper helpers). `apps/`, `configs/` and `validators.py` are fixtures the server runs, not helpers scripts source.
- No Python `subprocess` anywhere (apps start nothing).
- Every `uv run` carries `--frozen` so `uv.lock` never changes.
- Commit messages: imperative subject, body says why, no AI markers. One scenario (or one fix) per commit.
- Project gates before every commit that touches `lightapi/`, `tests/` or `pyproject.toml`: `uv run --frozen --extra dev ruff check lightapi tests examples`, `ruff format --check`, `mypy lightapi`, `pytest tests/ -q -p no:cacheprovider` (589 passed today; warnings are errors).
- The `autoecosystem_*` containers on this machine are never touched; the suite's Postgres is `lightapi-e2e-pg` on `127.0.0.1:55432`.
- Ports: scenario `N` runs on `18100 + index`; the e2e Docker container maps `18199`.

## Review Focus

Inputs the spec implies but no step exercised until this list was written; each has its test added to the owning task below.

1. A PUT that sends `version` as a JSON string (`"version": "1"`) must be coerced, not 422 or 500 (PR #46 behaviour). Task 1, step "version as string accepted".
2. `?search=` containing `%` or `_` must match literally, never as a wildcard. Task 6, steps "search percent literal" and "search underscore literal".
3. A cursor that is not base64 must give the first page, not 500. Task 7, step "invalid cursor is first page".
4. A PATCH on a reflected table without `version` must be 422 like a declared table. Task 11, step "reflected patch without version".
5. A duplicate `unique=True` value through PUT (not only POST) must be 409. Task 17, test `test_update_to_duplicate_unique_value_answers_409` and step "put to duplicate sku".

---

## Shared text used by every scenario task

### S1. Scenario script skeleton

Every `tools/e2e/scenarios/NN_<name>.sh` is this file with `NAME`, the second-line tag
comment, the default `DB_URL`, the pre-start block and the `STEPS` block replaced as the
task says. Nothing else changes between scenarios.

```bash
#!/usr/bin/env bash
# e2e: pg
# <one line: what this scenario proves>
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
    PASSED=$((PASSED + 1)); echo "PASS $1"
  else
    FAILED=$((FAILED + 1)); echo "FAIL $1: no header matching '$2': $(tr -d '\r' <"$OUT/headers" | tr '\n' ' ')"
  fi
}

# check <step> <arguments for test(1)>
check() {
  local step=$1
  shift
  if test "$@"; then
    PASSED=$((PASSED + 1)); echo "PASS $step"
  else
    FAILED=$((FAILED + 1)); echo "FAIL $step: test $* is false"
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
# ... scenario steps ...

# --- end ---
check "no traceback in server log" "$(grep -c Traceback "$OUT/server.log")" -eq 0
echo "== $NAME: $PASSED passed, $FAILED failed"
exit $((FAILED > 0))
```

Rules every script keeps:

- The second line is the tag comment `run_all.sh` reads: `# e2e:` followed by any of `pg`
  (also run against Postgres), `async` (the Postgres rerun uses the asyncpg URL), `pg-only`
  (no SQLite run), `docker` (only with `E2E_DOCKER=1`), or nothing (`# e2e:`).
- Table names in the app carry the scenario prefix (`e2e01_books`), and the pre-start block
  drops exactly those tables when `DB_URL` is Postgres.
- JSON requests pass `-H 'Content-Type: application/json'`; the task text abbreviates it as
  `$JSON`, so every script defines `JSON='Content-Type: application/json'` right after
  `FAILED=0` and uses `-H "$JSON"`.
- `$E2E_PSQL` is exported by `run_all.sh` (`psql postgresql://postgres:e2e@127.0.0.1:55432/postgres`);
  a script run alone against Postgres needs it exported by hand.

### S2. App skeleton

Every `tools/e2e/apps/<name>.py` starts and ends like this; the task gives the endpoint
classes and the `LightApi(...)` keyword arguments.

```python
"""e2e app for scenario <name>: <one line>."""

import os

from sqlalchemy import create_engine

from lightapi import Field, LightApi, RestEndpoint


class Book(RestEndpoint):
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    pages: int | None = Field(default=None)

    class Meta:
        table = "e2e01_books"


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/books": Book})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

An async app replaces the engine with
`from sqlalchemy.ext.asyncio import create_async_engine` and
`LightApi(engine=create_async_engine(os.environ["E2E_DB_URL"]), mode="async")`.

### S3. Running one scenario and the whole suite

```bash
tools/e2e/scenarios/01_crud_sync.sh                 # alone, SQLite, port 18100
E2E_PORT=18150 tools/e2e/scenarios/01_crud_sync.sh  # alone, another port
tools/e2e/run_all.sh                                # everything, SQLite + Postgres
tools/e2e/run_all.sh crud                           # scenarios whose name contains "crud"
E2E_DOCKER=1 tools/e2e/run_all.sh docker            # the image scenario
```

---

### Task 1: Harness and scenario 01 (CRUD, sync)

**Files:**
- Create: `tools/e2e/run_all.sh`, `tools/e2e/scenarios/01_crud_sync.sh`, `tools/e2e/apps/01_crud_sync.py`, `tools/e2e/README.md`
- Modify: `.gitignore` (add `tools/e2e/.out/`)

**Interfaces:**
- Produces: the skeleton S1 (every later scenario copies it), the tag convention on line 2, `run_all.sh` reading `# e2e:` tags, the env contract `E2E_PORT`, `E2E_DB_URL`, `E2E_OUT`, `E2E_PSQL`, `E2E_PG_URL`, `E2E_PG_ASYNC_URL`, `E2E_DOCKER`, `E2E_NO_DOCKER`.

- [ ] **Step 1: Ignore the output directory**

Append to `.gitignore`:

```
tools/e2e/.out/
```

- [ ] **Step 2: Write the app**

`tools/e2e/apps/01_crud_sync.py` is exactly S2.

- [ ] **Step 3: Write the scenario script**

`tools/e2e/scenarios/01_crud_sync.sh` is S1 with `NAME=01_crud_sync`, tag line `# e2e: pg`,
`JSON='Content-Type: application/json'` after `FAILED=0`, and this STEPS block:

```bash
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
```

- [ ] **Step 4: Run the script alone and read every line**

Run: `chmod +x tools/e2e/scenarios/01_crud_sync.sh && tools/e2e/scenarios/01_crud_sync.sh`
Expected: every line `PASS`, last line `== 01_crud_sync: 28 passed, 0 failed`, exit 0.
If a step fails, the body printed tells which expectation is wrong; fix the expectation
only when the behaviour is the documented one (README "Error responses" table), otherwise
it is a library bug: stop, write the failing unit test, fix, then continue.

- [ ] **Step 5: Write `run_all.sh`**

```bash
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
  command -v "$tool" >/dev/null || { echo "missing tool: $tool"; exit 1; }
done

HAVE_DOCKER=0
command -v docker >/dev/null && docker info >/dev/null 2>&1 && HAVE_DOCKER=1
PG_NAME=lightapi-e2e-pg
PG_PORT=55432
PG_READY=0
if [ $HAVE_DOCKER = 1 ]; then
  docker rm -f $PG_NAME >/dev/null 2>&1 || true
  docker run -d --rm --name $PG_NAME -e POSTGRES_PASSWORD=e2e -p 127.0.0.1:$PG_PORT:5432 postgres:16 >/dev/null
  trap 'docker rm -f $PG_NAME >/dev/null 2>&1' EXIT
  export E2E_PG_URL=postgresql+psycopg2://postgres:e2e@127.0.0.1:$PG_PORT/postgres
  export E2E_PG_ASYNC_URL=postgresql+asyncpg://postgres:e2e@127.0.0.1:$PG_PORT/postgres
  export E2E_PSQL="psql postgresql://postgres:e2e@127.0.0.1:$PG_PORT/postgres"
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
  until port_is_free "$port" || [ $tries -ge 5 ]; do port=$((port + 1)); tries=$((tries + 1)); done
  local log=$OUT/$label.log
  local status
  if env E2E_PORT=$port "$@" bash "$script" >"$log" 2>&1; then
    status=ok; ok=$((ok + 1))
  else
    status=FAIL; fail=$((fail + 1))
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
      if [ "${E2E_DOCKER:-0}" != 1 ]; then printf 'SKIP  %-26s set E2E_DOCKER=1 to run\n' "$name"; skipped=$((skipped + 1)); continue; fi ;;
  esac
  case $tags in
    *pg-only*) ;;
    *) run_one "$name" "$script" ;;
  esac
  case $tags in
    *pg*)
      if [ $HAVE_DOCKER = 1 ]; then
        case $tags in *async*) url=$E2E_PG_ASYNC_URL ;; *) url=$E2E_PG_URL ;; esac
        run_one "$name[pg]" "$script" E2E_DB_URL="$url"
      elif [ "${E2E_NO_DOCKER:-0}" = 1 ]; then
        printf 'SKIP  %-26s no docker\n' "$name[pg]"; skipped=$((skipped + 1))
      else
        printf 'FAIL  %-26s docker is required for [pg] runs (E2E_NO_DOCKER=1 to skip)\n' "$name[pg]"; fail=$((fail + 1))
      fi ;;
  esac
done

echo
echo "$ok ok, $fail failed, $skipped skipped. Logs in $OUT/"
exit $((fail > 0))
```

- [ ] **Step 6: Run the suite with only scenario 01**

Run: `chmod +x tools/e2e/run_all.sh && tools/e2e/run_all.sh crud`
Expected:
```
ok    01_crud_sync               28 passed, 0 failed
ok    01_crud_sync[pg]           28 passed, 0 failed

2 ok, 0 failed, 0 skipped. Logs in .../tools/e2e/.out/
```
If the `[pg]` run fails on "create" with a Postgres error about `created_at`, read
`.out/01_crud_sync[pg].log` and the server log: the table is created by `create_all` at
`build_app()`, so a failure here is a real bug.

- [ ] **Step 7: Write the README**

`tools/e2e/README.md`:

```markdown
# End-to-end curl suite

Real server process, real `curl`, throwaway databases. `tools/e2e/run_all.sh` runs every
`scenarios/*.sh` against a SQLite file, then again against a Postgres container
(`lightapi-e2e-pg`, 127.0.0.1:55432) for the scenarios tagged `pg`. Exit 0 only when every
step of every run passed.

    tools/e2e/run_all.sh            # everything (needs docker for the [pg] runs)
    tools/e2e/run_all.sh auth       # scenarios whose name contains "auth"
    E2E_NO_DOCKER=1 tools/e2e/run_all.sh   # skip the [pg] runs instead of failing them
    E2E_DOCKER=1 tools/e2e/run_all.sh docker   # build and probe the container image
    tools/e2e/scenarios/04_auth_jwt.sh         # one scenario alone, SQLite, port 18100

Needs: jq, curl, uv, sqlite3, psql, docker. Logs, response bodies and databases land in
`tools/e2e/.out/<scenario>/` (gitignored).

Each script is self-contained: it starts its app from `apps/<name>.py` (or
`python -m lightapi serve` on `configs/<name>.yaml`), waits for `/healthz`, runs its steps
with an inline `expect <step> <status> <jq filter> -- <curl args>`, and kills the server on
exit. Scripts share no helper file on purpose.

Environment the scripts read: `E2E_PORT` (default 18100), `E2E_DB_URL` (default a SQLite
file under `.out/`), `E2E_PSQL` (set by `run_all.sh` for the [pg] runs).

Known gaps: none. A step that pins a gap that cannot be fixed here would say so in this
section.
```

- [ ] **Step 8: Commit**

```bash
git add .gitignore tools/e2e/run_all.sh tools/e2e/README.md tools/e2e/scenarios/01_crud_sync.sh tools/e2e/apps/01_crud_sync.py
git commit -m "test(e2e): curl harness and the CRUD scenario on SQLite and Postgres

tools/e2e/run_all.sh serves each scenario app as a real process, drives
it with curl and jq, and reruns the pg-tagged scenarios against a
throwaway postgres:16 container. 01_crud_sync covers create, read,
update with optimistic locking, partial update, validation errors and
the 404/409/422 replies the README documents."
```

---

### Task 2: Scenario 02, the same CRUD on the async path

**Files:**
- Create: `tools/e2e/scenarios/02_crud_async.sh`, `tools/e2e/apps/02_crud_async.py`

- [ ] **Step 1: App**

`tools/e2e/apps/02_crud_async.py` is S2 with the async engine
(`create_async_engine(os.environ["E2E_DB_URL"])`, `mode="async"`) and `table = "e2e02_books"`.

- [ ] **Step 2: Script**

Copy `01_crud_sync.sh` to `02_crud_async.sh`; change `NAME=02_crud_async`, the tag line to
`# e2e: pg async`, the default to `DB_URL=${E2E_DB_URL:-sqlite+aiosqlite:///$OUT/db.sqlite}`,
and the drop statement to `e2e02_books`. The STEPS block is identical to Task 1.

- [ ] **Step 3: Run alone, then through run_all**

Run: `tools/e2e/scenarios/02_crud_async.sh && tools/e2e/run_all.sh crud`
Expected: `28 passed, 0 failed` for `02_crud_async` and `02_crud_async[pg]` (asyncpg). The
async app creates its tables in the lifespan, so a "no such table" on the first POST means
the lifespan did not run: check `server.log`.

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/02_crud_async.sh tools/e2e/apps/02_crud_async.py
git commit -m "test(e2e): the CRUD scenario on an async engine, aiosqlite and asyncpg"
```

---

### Task 3: Scenario 03, HttpMethod mixins and the four Serializer forms

**Files:**
- Create: `tools/e2e/scenarios/03_mixins_serializer.sh`, `tools/e2e/apps/03_mixins_serializer.py`

- [ ] **Step 1: App**

```python
"""e2e app for scenario 03: HttpMethod mixins and Serializer forms."""

import os

from sqlalchemy import create_engine

from lightapi import Field, HttpMethod, LightApi, RestEndpoint, Serializer


class ReadOnlyNote(RestEndpoint, HttpMethod.GET):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e03_notes"


class Event(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    name: str = Field(min_length=1)

    class Meta:
        table = "e2e03_events"


class PublicUser(RestEndpoint):
    name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    secret: str = Field(min_length=1)

    class Meta:
        table = "e2e03_users"
        serializer = Serializer(fields=["id", "name", "email"])


class Order(RestEndpoint):
    name: str = Field(min_length=1)
    tag: str = Field(default="")

    class Meta:
        table = "e2e03_orders"
        serializer = Serializer(read=["id", "name", "tag"], write=["id", "name"])


class NameOnly(Serializer):
    read = ["id", "name"]
    write = ["id", "name"]


class Alpha(RestEndpoint):
    name: str = Field(min_length=1)
    extra: str = Field(default="")

    class Meta:
        table = "e2e03_alpha"
        serializer = NameOnly


class Beta(RestEndpoint):
    name: str = Field(min_length=1)
    extra: str = Field(default="")

    class Meta:
        table = "e2e03_beta"
        serializer = NameOnly


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register(
        {
            "/notes": ReadOnlyNote,
            "/events": Event,
            "/users": PublicUser,
            "/orders": Order,
            "/alpha": Alpha,
            "/beta": Beta,
        }
    )
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Script** (tag `# e2e:`, drop list `e2e03_notes, e2e03_events, e2e03_users, e2e03_orders, e2e03_alpha, e2e03_beta`)

```bash
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
expect "fields=: post hides secret" 201 '(keys|sort)==["email","id","name"]' -- -X POST -H "$JSON" -d '{"name":"ana","email":"a@x","secret":"hunter2"}' "$BASE/users"
expect "fields=: get hides secret" 200 '(.results[0]|keys|sort)==["email","id","name"]' -- "$BASE/users"
expect "read/write: post shows write fields" 201 '(keys|sort)==["id","name"]' -- -X POST -H "$JSON" -d '{"name":"o1","tag":"vip"}' "$BASE/orders"
expect "read/write: get shows read fields" 200 '(keys|sort)==["id","name","tag"] and .tag=="vip"' -- "$BASE/orders/1"
expect "read/write: list shows read fields" 200 '(.results[0]|keys|sort)==["id","name","tag"]' -- "$BASE/orders"
expect "subclass: alpha post" 201 '(keys|sort)==["id","name"]' -- -X POST -H "$JSON" -d '{"name":"a","extra":"hidden"}' "$BASE/alpha"
expect "subclass: beta post" 201 '(keys|sort)==["id","name"]' -- -X POST -H "$JSON" -d '{"name":"b","extra":"hidden"}' "$BASE/beta"
expect "subclass: alpha get" 200 '(keys|sort)==["id","name"]' -- "$BASE/alpha/1"
expect "subclass: beta get" 200 '(keys|sort)==["id","name"]' -- "$BASE/beta/1"
```

The 405 on a detail route of a GET+POST endpoint says `Allowed: GET` because the detail
route of that class only has GET; if the server answers `Allowed: GET, POST` the handler
is listing the collection verbs on the detail route, a bug to fix (test in
`tests/test_rest.py`), not an expectation to relax.

- [ ] **Step 3: Run alone**

Run: `tools/e2e/scenarios/03_mixins_serializer.sh`
Expected: `20 passed, 0 failed`.

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/03_mixins_serializer.sh tools/e2e/apps/03_mixins_serializer.py
git commit -m "test(e2e): HttpMethod mixins answer 405 with Allow; Serializer forms project fields"
```

---

### Task 4: Fix the documented 403 body, then scenario 04 (JWT, permissions)

**Files:**
- Modify: `README.md:988`, `docs/api-reference/rest.md:222`
- Create: `tools/e2e/scenarios/04_auth_jwt.sh`, `tools/e2e/apps/04_auth_jwt.py`, `tools/e2e/validators.py`

- [ ] **Step 1: Correct the docs**

In both files replace the 403 row's body with what the code answers:

```
| Permission denied | `403` | `{"detail": "Insufficient permissions"}` |
```

Run `uv run --frozen --extra dev mkdocs build --strict -q` (exit 0), then commit:

```bash
git add README.md docs/api-reference/rest.md
git commit -m "docs: the 403 body is \"Insufficient permissions\"

README and the REST reference showed a sentence the code never sent;
v0.1.29 and today both answer {\"detail\": \"Insufficient permissions\"}."
```

- [ ] **Step 2: The validators module** (shared by the Python apps and the YAML scenario, imported by dotted path)

`tools/e2e/validators.py`:

```python
"""Login validators the e2e apps and YAML documents use (PYTHONPATH=tools/e2e)."""

USERS = {
    "admin": ("secret", {"sub": "1", "username": "admin", "is_admin": True}),
    "user": ("password", {"sub": "2", "username": "user", "is_admin": False}),
}


def check_login(username: str, password: str) -> dict | None:
    known = USERS.get(username)
    if known is None or known[0] != password:
        return None
    return known[1]
```

- [ ] **Step 3: App**

```python
"""e2e app for scenario 04: JWT login, permissions per method, extra claims."""

import os

from sqlalchemy import create_engine
from validators import check_login

from lightapi import (
    AllowAny,
    Authentication,
    Field,
    IsAdminUser,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    RestEndpoint,
)


class Secret(RestEndpoint):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e04_secrets"
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
            jwt_expiration=120,
            jwt_extra_claims=["is_admin"],
        )


class AdminOnly(RestEndpoint):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e04_admin"
        authentication = Authentication(backend=JWTAuthentication, permission=IsAdminUser)


class Mixed(RestEndpoint):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e04_mixed"
        authentication = Authentication(
            backend=JWTAuthentication,
            permission={"GET": AllowAny, "POST": IsAuthenticated, "DELETE": IsAdminUser},
        )


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]), login_validator=check_login)
    app.register({"/secrets": Secret, "/admin": AdminOnly, "/mixed": Mixed})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

`Secret` is registered first on purpose: the login route builds its tokens with the first
JWT backend, so `jwt_expiration=120` and `jwt_extra_claims` are the ones the token shows.

- [ ] **Step 4: Script** (tag `# e2e:`, drop `e2e04_secrets, e2e04_admin, e2e04_mixed`)

```bash
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
expect "login bad password" 401 '.detail=="Invalid credentials"' -- -X POST -H "$JSON" -d '{"username":"admin","password":"wrong"}' "$BASE/auth/login"
expect "login unknown user" 401 '.detail=="Invalid credentials"' -- -X POST -H "$JSON" -d '{"username":"ghost","password":"x"}' "$BASE/auth/login"
expect "login missing field" 422 '' -- -X POST -H "$JSON" -d '{"username":"admin"}' "$BASE/auth/login"
expect "login get is 405" 405 '' -- "$BASE/auth/login"
header "login 405 allow" '^allow: POST'
expect "login user" 200 '(.token|type)=="string" and .user.username=="user" and .user.is_admin==false' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
USER_TOKEN=$(body .token)
expect "login admin" 200 '(.token|type)=="string" and .user.is_admin==true' -- -X POST -H "$JSON" -d '{"username":"admin","password":"secret"}' "$BASE/auth/login"
ADMIN_TOKEN=$(body .token)
expect "token alias route" 200 '(.token|type)=="string"' -- -X POST -H "$JSON" -d '{"username":"admin","password":"secret"}' "$BASE/auth/token"

# the payload is the middle base64url segment; pad it for the decoder
PAYLOAD=$(echo "$ADMIN_TOKEN" | cut -d. -f2 | tr '_-' '/+')
PAYLOAD_JSON=$(printf '%s' "$PAYLOAD" | awk '{ while (length($0) % 4) $0 = $0 "="; print }' | base64 -d 2>/dev/null)
check "token carries the extra claim" "$(printf '%s' "$PAYLOAD_JSON" | jq -r .is_admin)" = true
check "token expires in about 120s" "$(printf '%s' "$PAYLOAD_JSON" | jq -r '(.exp - now) | floor')" -gt 100

expect "secrets without token" 401 '.detail=="Authentication credentials invalid."' -- "$BASE/secrets"
header "secrets 401 www-authenticate" '^www-authenticate: Bearer'
expect "secrets tampered token" 401 '.detail=="Authentication credentials invalid."' -- -H "Authorization: Bearer ${USER_TOKEN%?}x" "$BASE/secrets"
expect "secrets wrong scheme" 401 '' -- -H "Authorization: Basic dXNlcjpwYXNzd29yZA==" "$BASE/secrets"
expect "secrets with token" 200 '.results==[]' -- -H "Authorization: Bearer $USER_TOKEN" "$BASE/secrets"
expect "secrets post with token" 201 '.text=="s1"' -- -X POST -H "$JSON" -H "Authorization: Bearer $USER_TOKEN" -d '{"text":"s1"}' "$BASE/secrets"

EXPIRED=$(uv run --frozen --extra dev --directory "$ROOT" python -c "import jwt,datetime; print(jwt.encode({'sub':'2','exp':datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=5)}, 'e2e-secret', algorithm='HS256'))")
expect "secrets expired token" 401 '.detail=="Authentication credentials invalid."' -- -H "Authorization: Bearer $EXPIRED" "$BASE/secrets"

expect "admin as user is 403" 403 '.detail=="Insufficient permissions"' -- -H "Authorization: Bearer $USER_TOKEN" "$BASE/admin"
expect "admin post as user is 403" 403 '.detail=="Insufficient permissions"' -- -X POST -H "$JSON" -H "Authorization: Bearer $USER_TOKEN" -d '{"text":"x"}' "$BASE/admin"
expect "admin as admin" 200 '.results==[]' -- -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/admin"
expect "admin without token" 401 '' -- "$BASE/admin"

expect "mixed: anonymous get" 200 '.results==[]' -- "$BASE/mixed"
expect "mixed: anonymous post" 401 '' -- -X POST -H "$JSON" -d '{"text":"x"}' "$BASE/mixed"
expect "mixed: user post" 201 '.id==1' -- -X POST -H "$JSON" -H "Authorization: Bearer $USER_TOKEN" -d '{"text":"x"}' "$BASE/mixed"
expect "mixed: anonymous get detail" 200 '.id==1' -- "$BASE/mixed/1"
expect "mixed: user delete is 403" 403 '.detail=="Insufficient permissions"' -- -X DELETE -H "Authorization: Bearer $USER_TOKEN" "$BASE/mixed/1"
expect "mixed: admin delete" 204 '' -- -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/mixed/1"
```

- [ ] **Step 5: Run alone**

Run: `tools/e2e/scenarios/04_auth_jwt.sh`
Expected: `32 passed, 0 failed`. The "wrong scheme" step: a `Basic` header on a JWT
endpoint must be 401, never 500.

- [ ] **Step 6: Commit**

```bash
git add tools/e2e/validators.py tools/e2e/scenarios/04_auth_jwt.sh tools/e2e/apps/04_auth_jwt.py
git commit -m "test(e2e): JWT login, token claims and expiry, permissions per method"
```

---

### Task 5: Scenario 05, Basic authentication

**Files:**
- Create: `tools/e2e/scenarios/05_auth_basic.sh`, `tools/e2e/apps/05_auth_basic.py`

- [ ] **Step 1: App**

```python
"""e2e app for scenario 05: BasicAuthentication with its own validate_credentials."""

import os

from sqlalchemy import create_engine
from validators import check_login

from lightapi import Authentication, BasicAuthentication, Field, IsAuthenticated, LightApi, RestEndpoint


class E2EBasic(BasicAuthentication):
    def validate_credentials(self, username: str, password: str) -> dict | None:
        return check_login(username, password)


class Ledger(RestEndpoint):
    entry: str = Field(min_length=1)

    class Meta:
        table = "e2e05_ledger"
        authentication = Authentication(backend=E2EBasic, permission=IsAuthenticated)


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/ledger": Ledger})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

No `login_validator` on the app: the subclass's `validate_credentials` must be what the
guard and the login route call.

- [ ] **Step 2: Script** (tag `# e2e:`, drop `e2e05_ledger`)

```bash
GOOD=$(printf 'admin:secret' | base64)
BAD=$(printf 'admin:nope' | base64)
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
expect "no header" 401 '.error=="authentication failed"' -- "$BASE/ledger"
header "challenge" '^www-authenticate: Basic realm='
expect "bad password" 401 '.error=="authentication failed"' -- -H "Authorization: Basic $BAD" "$BASE/ledger"
expect "garbage header" 401 '' -- -H "Authorization: Basic not-base64!" "$BASE/ledger"
expect "bearer on a basic endpoint" 401 '' -- -H "Authorization: Bearer abc" "$BASE/ledger"
expect "good credentials" 200 '.results==[]' -- -H "Authorization: Basic $GOOD" "$BASE/ledger"
expect "good credentials post" 201 '.entry=="first"' -- -X POST -H "$JSON" -H "Authorization: Basic $GOOD" -d '{"entry":"first"}' "$BASE/ledger"
expect "login route with basic backend" 200 '.user.username=="admin" and (has("token")|not)' -- -X POST -H "$JSON" -d '{"username":"admin","password":"secret"}' "$BASE/auth/login"
expect "login route bad password" 401 '.detail=="Invalid credentials"' -- -X POST -H "$JSON" -d '{"username":"admin","password":"x"}' "$BASE/auth/login"
```

- [ ] **Step 3: Run alone**

Run: `tools/e2e/scenarios/05_auth_basic.sh`
Expected: `11 passed, 0 failed`.

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/05_auth_basic.sh tools/e2e/apps/05_auth_basic.py
git commit -m "test(e2e): Basic authentication through a validate_credentials subclass"
```

---

### Task 6: Scenario 06, filtering, search, ordering with pagination

**Files:**
- Create: `tools/e2e/scenarios/06_filtering.sh`, `tools/e2e/apps/06_filtering.py`

- [ ] **Step 1: App**

```python
"""e2e app for scenario 06: FieldFilter, SearchFilter, OrderingFilter and page pagination."""

import os

from sqlalchemy import create_engine

from lightapi import Field, FieldFilter, Filtering, LightApi, OrderingFilter, Pagination, RestEndpoint, SearchFilter


class Book(RestEndpoint):
    title: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    price: float = Field()
    pages: int = Field()
    published: bool = Field(default=True)

    class Meta:
        table = "e2e06_books"
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["genre", "published", "pages"],
            search=["title"],
            ordering=["price", "pages"],
        )
        pagination = Pagination(page_size=5)


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/books": Book})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Script** (tag `# e2e: pg`, drop `e2e06_books`)

```bash
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
expect "filter int garbage is literal" 200 '.count==0' -- "$BASE/books?pages=lots"
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
```

- [ ] **Step 3: Run alone and through run_all**

Run: `tools/e2e/scenarios/06_filtering.sh && tools/e2e/run_all.sh filtering`
Expected: `18 passed, 0 failed` on SQLite and `[pg]`. On Postgres `ilike` and float
rendering are the parts that can differ from SQLite: a `price==45.5` mismatch is a
serialization difference worth reporting, not an expectation to loosen.

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/06_filtering.sh tools/e2e/apps/06_filtering.py
git commit -m "test(e2e): field, search and ordering filters combined with page pagination"
```

---

### Task 7: Scenario 07, page-number and cursor pagination

**Files:**
- Create: `tools/e2e/scenarios/07_pagination.sh`, `tools/e2e/apps/07_pagination.py`

- [ ] **Step 1: App**

```python
"""e2e app for scenario 07: page-number and cursor pagination."""

import os

from sqlalchemy import create_engine

from lightapi import Field, LightApi, Pagination, RestEndpoint


class PageItem(RestEndpoint):
    label: str = Field(min_length=1)

    class Meta:
        table = "e2e07_page_items"
        pagination = Pagination(page_size=2)


class CursorItem(RestEndpoint):
    label: str = Field(min_length=1)

    class Meta:
        table = "e2e07_cursor_items"
        pagination = Pagination(style="cursor", page_size=2)


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/pages": PageItem, "/cursor": CursorItem})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Script** (tag `# e2e:`, drop `e2e07_page_items, e2e07_cursor_items`)

```bash
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
```

- [ ] **Step 3: Run alone**

Run: `tools/e2e/scenarios/07_pagination.sh`
Expected: `17 passed, 0 failed`. The `next`/`previous` URLs carry the host and port the
server sees, so the `endswith` checks are what to compare, not the whole URL.

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/07_pagination.sh tools/e2e/apps/07_pagination.py
git commit -m "test(e2e): page-number links and a full cursor walk over 25 rows"
```

---

### Task 8: Scenario 08, the three queryset forms on an async app

**Files:**
- Create: `tools/e2e/scenarios/08_queryset.sh`, `tools/e2e/apps/08_queryset.py`

- [ ] **Step 1: App**

```python
"""e2e app for scenario 08: static, sync and async queryset hooks on one async app."""

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request

from lightapi import Field, LightApi, RestEndpoint


class StaticArticle(RestEndpoint):
    title: str = Field(min_length=1)
    published: bool = Field(default=False)

    class Meta:
        table = "e2e08_static"


class SyncArticle(RestEndpoint):
    title: str = Field(min_length=1)
    published: bool = Field(default=False)

    class Meta:
        table = "e2e08_sync"

    def queryset(self, request: Request):
        model = type(self)._model_class
        return select(model).where(model.published.is_(True))


class AsyncArticle(RestEndpoint):
    title: str = Field(min_length=1)
    published: bool = Field(default=False)
    words: int = Field(default=0)

    class Meta:
        table = "e2e08_async"

    async def queryset(self, request: Request):
        model = type(self)._model_class
        stmt = select(model).where(model.published.is_(True))
        minimum = request.query_params.get("min_words")
        if minimum is not None:
            stmt = stmt.where(model.words >= int(minimum))
        return stmt


def main() -> None:
    app = LightApi(engine=create_async_engine(os.environ["E2E_DB_URL"]), mode="async")
    app.register({"/static": StaticArticle, "/sync": SyncArticle, "/async": AsyncArticle})
    # The static form needs the mapped class, which exists only after register().
    StaticArticle.queryset = select(StaticArticle._model_class).where(
        StaticArticle._model_class.published.is_(True)
    )
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Script** (tag `# e2e: async`, default `sqlite+aiosqlite:///`, drop `e2e08_static, e2e08_sync, e2e08_async`)

```bash
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
for route in static sync async; do
  curl -s -o /dev/null -X POST -H "$JSON" -d '{"title":"draft","published":false}' "$BASE/$route"
  curl -s -o /dev/null -X POST -H "$JSON" -d '{"title":"live one","published":true,"words":100}' "$BASE/$route"
  curl -s -o /dev/null -X POST -H "$JSON" -d '{"title":"live two","published":true,"words":900}' "$BASE/$route"
done
expect "static: list shows published only" 200 '(.results|length)==2 and all(.results[]; .published==true)' -- "$BASE/static"
expect "sync: list shows published only" 200 '(.results|length)==2 and all(.results[]; .published==true)' -- "$BASE/sync"
expect "async: list shows published only" 200 '(.results|length)==2' -- "$BASE/async"
expect "async: query parameter reaches the hook" 200 '(.results|length)==1 and .results[0].words==900' -- "$BASE/async?min_words=500"
expect "async: hook that excludes all" 200 '.results==[]' -- "$BASE/async?min_words=5000"
expect "static: retrieve ignores the queryset" 200 '.id==1 and .published==false' -- "$BASE/static/1"
expect "sync: retrieve ignores the queryset" 200 '.id==1 and .published==false' -- "$BASE/sync/1"
expect "async: retrieve ignores the queryset" 200 '.id==1 and .published==false' -- "$BASE/async/1"
expect "async: post still works" 201 '.id==4' -- -X POST -H "$JSON" -d '{"title":"new","published":true}' "$BASE/async"
expect "async: patch a filtered-out row" 200 '.version==2' -- -X PATCH -H "$JSON" -d '{"title":"draft2","version":1}' "$BASE/async/1"
```

- [ ] **Step 3: Run alone**

Run: `tools/e2e/scenarios/08_queryset.sh`
Expected: `11 passed, 0 failed`. "retrieve ignores the queryset" pins today's contract
(`tests/test_queryset.py` says the same); do not change it here.

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/08_queryset.sh tools/e2e/apps/08_queryset.py
git commit -m "test(e2e): static, sync and async queryset hooks filter the list route"
```

---

### Task 9: Scenario 09, middleware chain and CORS

**Files:**
- Create: `tools/e2e/scenarios/09_middleware.sh`, `tools/e2e/apps/09_middleware.py`

- [ ] **Step 1: App**

```python
"""e2e app for scenario 09: sync and async Middleware in one chain, short-circuit, CORS."""

import os

from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi import Field, LightApi, Middleware, RestEndpoint


class Stamp(Middleware):
    def process(self, request: Request, response: Response | None) -> Response | None:
        if response is None:
            print("hook pre:stamp", flush=True)
            return None
        response.headers["x-e2e-stamp"] = "yes"
        print("hook post:stamp", flush=True)
        return response


class Trace(Middleware):
    async def process(self, request: Request, response: Response | None) -> Response | None:
        print("hook pre:trace" if response is None else "hook post:trace", flush=True)
        return response


class Teapot(Middleware):
    def process(self, request: Request, response: Response | None) -> Response | None:
        if response is None and request.headers.get("x-teapot"):
            return JSONResponse({"detail": "teapot"}, status_code=418)
        return response


class Item(RestEndpoint):
    name: str = Field(min_length=1)

    class Meta:
        table = "e2e09_items"


def main() -> None:
    app = LightApi(
        engine=create_async_engine(os.environ["E2E_DB_URL"]),
        mode="async",
        middlewares=[Stamp, Trace, Teapot],
        cors_origins=["http://e2e.local"],
    )
    app.register({"/items": Item})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Script** (tag `# e2e: async`, default `sqlite+aiosqlite:///`, drop `e2e09_items`)

```bash
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
expect "post through the chain" 201 '.name=="a"' -- -X POST -H "$JSON" -d '{"name":"a"}' "$BASE/items"
header "post-hook header" '^x-e2e-stamp: yes'
expect "get through the chain" 200 '(.results|length)==1' -- "$BASE/items"
header "post-hook header on get" '^x-e2e-stamp: yes'
sleep 0.2
check "pre hooks run in declaration order" "$(grep -E '^hook pre:' "$OUT/server.log" | head -2 | tr '\n' ' ')" = "hook pre:stamp hook pre:trace "
check "post hooks run last registered first" "$(grep -E '^hook post:' "$OUT/server.log" | head -2 | tr '\n' ' ')" = "hook post:trace hook post:stamp "
expect "short-circuit answers before the endpoint" 418 '.detail=="teapot"' -- -X POST -H "$JSON" -H 'x-teapot: 1' -d '{"name":"never"}' "$BASE/items"
expect "short-circuit wrote nothing" 200 '(.results|length)==1' -- "$BASE/items"
expect "cors header for an allowed origin" 200 '' -- -H 'Origin: http://e2e.local' "$BASE/items"
header "access-control-allow-origin" '^access-control-allow-origin: http://e2e.local'
expect "cors preflight" 200 '' -- -X OPTIONS -H 'Origin: http://e2e.local' -H 'Access-Control-Request-Method: POST' "$BASE/items"
header "preflight allows POST" '^access-control-allow-methods: .*POST'
expect "cors unknown origin gets no header" 200 '' -- -H 'Origin: http://evil.local' "$BASE/items"
check "no allow-origin for unknown origin" "$(grep -ci '^access-control-allow-origin' "$OUT/headers")" -eq 0
```

- [ ] **Step 3: Run alone**

Run: `tools/e2e/scenarios/09_middleware.sh`
Expected: `15 passed, 0 failed`.

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/09_middleware.sh tools/e2e/apps/09_middleware.py
git commit -m "test(e2e): middleware order, short-circuit and CORS on an async app"
```

---

### Task 10: Scenario 10, background tasks

**Files:**
- Create: `tools/e2e/scenarios/10_background.sh`, `tools/e2e/apps/10_background.py`

- [ ] **Step 1: App**

```python
"""e2e app for scenario 10: self.background() with a sync and an async function."""

import asyncio
import json
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request

from lightapi import Field, LightApi, RestEndpoint

MARKS = Path(os.environ["E2E_OUT"]) / "marks"


def mark_sync(item_id: int) -> None:
    (MARKS / f"sync-{item_id}").write_text(str(item_id))


async def mark_async(item_id: int) -> None:
    await asyncio.sleep(0.05)
    (MARKS / f"async-{item_id}").write_text(str(item_id))


class Job(RestEndpoint):
    name: str = Field(min_length=1)

    class Meta:
        table = "e2e10_jobs"

    async def post(self, request: Request):
        response = await self._create_async(json.loads(await request.body()))
        item_id = json.loads(response.body)["id"]
        self.background(mark_sync, item_id)
        self.background(mark_async, item_id)
        return response


def main() -> None:
    MARKS.mkdir(parents=True, exist_ok=True)
    app = LightApi(engine=create_async_engine(os.environ["E2E_DB_URL"]), mode="async")
    app.register({"/jobs": Job})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Script** (tag `# e2e: async`, default `sqlite+aiosqlite:///`, drop `e2e10_jobs`; pre-start also runs `rm -rf "$OUT/marks"`)

```bash
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
expect "post returns at once" 201 '.id==1 and .name=="first"' -- -X POST -H "$JSON" -d '{"name":"first"}' "$BASE/jobs"
for _ in $(seq 1 20); do [ -f "$OUT/marks/sync-1" ] && [ -f "$OUT/marks/async-1" ] && break; sleep 0.1; done
check "sync task ran" -f "$OUT/marks/sync-1"
check "async task ran" -f "$OUT/marks/async-1"
check "task saw the new id" "$(cat "$OUT/marks/async-1")" = 1
expect "second post" 201 '.id==2' -- -X POST -H "$JSON" -d '{"name":"second"}' "$BASE/jobs"
for _ in $(seq 1 20); do [ -f "$OUT/marks/async-2" ] && break; sleep 0.1; done
check "tasks are per request" "$(ls "$OUT/marks" | wc -l | tr -d ' ')" -eq 4
expect "row is stored" 200 '(.results|length)==2' -- "$BASE/jobs"
```

- [ ] **Step 3: Run alone**

Run: `tools/e2e/scenarios/10_background.sh`
Expected: `8 passed, 0 failed`.

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/10_background.sh tools/e2e/apps/10_background.py
git commit -m "test(e2e): background tasks run after the response, sync and async"
```

---

### Task 11: Scenario 11, table reflection (full, partial, missing)

**Files:**
- Create: `tools/e2e/scenarios/11_reflection.sh`, `tools/e2e/apps/11_reflection.py`, `tools/e2e/apps/11_reflection_missing.py`

- [ ] **Step 1: Apps**

`tools/e2e/apps/11_reflection.py`:

```python
"""e2e app for scenario 11: endpoints mapped onto tables that already exist."""

import os

from sqlalchemy import create_engine

from lightapi import Field, LightApi, RestEndpoint


class Product(RestEndpoint):
    class Meta:
        table = "e2e11_products"
        reflect = True


class Doc(RestEndpoint):
    notes: str = Field(default="")

    class Meta:
        table = "e2e11_docs"
        reflect = "partial"


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/products": Product, "/docs": Doc})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

`tools/e2e/apps/11_reflection_missing.py`:

```python
"""e2e app for scenario 11: reflecting a table that does not exist must refuse to start."""

import os

from sqlalchemy import create_engine

from lightapi import LightApi, RestEndpoint


class Ghost(RestEndpoint):
    class Meta:
        table = "e2e11_ghost"
        reflect = True


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/ghost": Ghost})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Script** (tag `# e2e: pg`)

The pre-start block creates the tables instead of only dropping them:

```bash
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
```

STEPS:

```bash
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
  uv run --frozen --extra dev --directory "$ROOT" python "$E2E/apps/11_reflection_missing.py" >"$MISSING_LOG" 2>&1
check "missing table: process exits non-zero" $? -ne 0
check "missing table: ConfigurationError in the log" "$(grep -c 'ConfigurationError' "$MISSING_LOG")" -ge 1
check "missing table: the message names the table" "$(grep -c 'e2e11_ghost' "$MISSING_LOG")" -ge 1
```

- [ ] **Step 3: Run alone and through run_all**

Run: `tools/e2e/scenarios/11_reflection.sh && tools/e2e/run_all.sh reflection`
Expected: `18 passed, 0 failed` on SQLite and `[pg]`. The server log for the main
process must have no `Traceback` (the missing-table log is separate and is allowed one).

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/11_reflection.sh tools/e2e/apps/11_reflection.py tools/e2e/apps/11_reflection_missing.py
git commit -m "test(e2e): full and partial reflection on SQLite and Postgres; a missing table refuses to start"
```

---

### Task 12: Fix B6-001 (async mode from a URL), then scenario 12 (YAML + `lightapi serve`)

**Files:**
- Modify: `lightapi/lightapi.py` (`__init__`, `_engine_from_url`)
- Test: `tests/test_audit.py` (new class `TestB6AsyncFromUrl`)
- Create: `tools/e2e/configs/12_yaml_serve.yaml`, `tools/e2e/configs/12_yaml_async.yaml`, `tools/e2e/scenarios/12_yaml_serve.sh`

**Interfaces:**
- Produces: `LightApi(database_url=..., mode="async")` builds an `AsyncEngine`; `LightApi._engine_from_url(database_url: str | None, mode: ExecutionMode) -> Engine | AsyncEngine`.

- [ ] **Step 1: Failing tests**

Append to `tests/test_audit.py` (imports `ExecutionMode` are not needed; `LightApi`, `RestEndpoint`, `LField`, `TestClient`, `ConfigurationError`, `LightAPIConfig` already imported there):

```python
class TestB6AsyncFromUrl:
    def test_async_mode_with_a_database_url_builds_an_async_engine(self):
        """B6-001: mode='async' plus database_url used to raise at register()."""

        class AuditUrlAsync(RestEndpoint):
            title: str = LField()

        app = LightApi(database_url="sqlite+aiosqlite:///:memory:", mode="async")
        app.register({"/urlasync": AuditUrlAsync})

        with TestClient(app.build_app()) as client:
            assert client.post("/urlasync", json={"title": "t"}).status_code == 201
            assert client.get("/urlasync").json()["results"][0]["title"] == "t"

    def test_async_mode_with_a_sync_driver_url_is_a_configuration_error(self):
        with pytest.raises(ConfigurationError, match="async driver"):
            LightApi(database_url="sqlite:///:memory:", mode="async")

    def test_from_config_serves_an_async_document(self, tmp_path):
        document = tmp_path / "async.yaml"
        document.write_text(
            'database:\n  url: "sqlite+aiosqlite:///:memory:"\nmode: async\nendpoints:\n'
            "  - route: /asyncdocs\n    fields:\n      title: {type: str}\n"
        )

        app = LightApi.from_config(str(document))

        with TestClient(app.build_app()) as client:
            assert client.post("/asyncdocs", json={"title": "y"}).status_code == 201
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run --frozen --extra dev pytest tests/test_audit.py -q -k B6AsyncFromUrl -p no:cacheprovider`
Expected: 3 failed, each with `ConfigurationError: mode='async' requires AsyncEngine, got Engine` (the third may fail the same way inside `from_config`).

- [ ] **Step 3: Implement**

In `lightapi/lightapi.py` `__init__`, compute the mode before the engine and pass it:

```python
        self._mode = ExecutionMode.from_user(mode)
        # Sync or async is a runtime fact (ExecutionMode), so the attribute is loose.
        self._engine: Any = (
            engine
            if engine is not None
            else self._engine_from_url(database_url, self._mode)
        )
```

(remove the later `self._mode = ExecutionMode.from_user(mode)` line) and replace
`_engine_from_url`:

```python
    @staticmethod
    def _engine_from_url(
        database_url: str | None, mode: ExecutionMode
    ) -> Engine | AsyncEngine:
        url = database_url or os.environ.get("LIGHTAPI_DATABASE_URL")
        if url is None:
            raise ConfigurationError(
                "No database configured. Provide engine=..., database_url=..., or set "
                "LIGHTAPI_DATABASE_URL environment variable."
            )
        if mode is not ExecutionMode.ASYNC:
            return create_engine(url)
        # sqlalchemy[asyncio] is the optional `async` extra.
        from sqlalchemy.ext.asyncio import create_async_engine

        try:
            return create_async_engine(url)
        except InvalidRequestError as exc:
            raise ConfigurationError(
                f"mode='async' needs an async driver in the database URL "
                f"(sqlite+aiosqlite://, postgresql+asyncpg://), got '{url}'."
            ) from exc
```

Add `from sqlalchemy.exc import InvalidRequestError, SQLAlchemyError` to the existing
`sqlalchemy.exc` import. `AsyncEngine` is already imported under `TYPE_CHECKING`.

- [ ] **Step 4: Run the tests and the gates**

Run: `uv run --frozen --extra dev pytest tests/ -q -p no:cacheprovider && uv run --frozen --extra dev ruff check lightapi tests && uv run --frozen --extra dev ruff format --check lightapi tests && uv run --frozen --extra dev mypy lightapi`
Expected: 592 passed, everything clean.

- [ ] **Step 5: Update CHANGELOG and the audit doc, commit the fix**

CHANGELOG `[Unreleased]` / `### Fixed`:

```
- **`mode="async"` works from a database URL**: `LightApi(database_url=..., mode="async")`
  and a YAML document with `mode: async` build an `AsyncEngine`, so `lightapi serve` can
  start an async app. Before, both failed at `register()` with "requires AsyncEngine". A
  URL without an async driver now raises `ConfigurationError` naming the fix.
```

`docs/audit.md` row `B6-001`: status `corrigido`, commit hash, decision text
"corrigido: `_engine_from_url` builds an `AsyncEngine` in async mode".

```bash
git add lightapi/lightapi.py tests/test_audit.py CHANGELOG.md docs/audit.md
git commit -m "fix(B6-001): mode='async' builds an AsyncEngine from the database URL

LightApi(database_url=..., mode=\"async\") and a YAML document with
mode: async raised at register() because the URL was always opened with
create_engine. The mode now picks create_async_engine; a URL without an
async driver is a ConfigurationError that says which drivers work."
```

- [ ] **Step 6: The YAML documents**

`tools/e2e/configs/12_yaml_serve.yaml` (`@DB@` is replaced by the script):

```yaml
database:
  url: "@DB@"

mode: sync

auth:
  auth_path: /auth
  login_validator: validators.check_login

defaults:
  pagination: { style: page_number, page_size: 3 }
  filtering:
    backends: [FieldFilter, SearchFilter, OrderingFilter]
    fields: [genre]
    search: [title]
    ordering: [pages]

endpoints:
  - route: /books
    fields:
      title: { type: str, min_length: 1, max_length: 40 }
      genre: { type: str, default: "general" }
      pages: { type: int, optional: true }
      rating: { type: float, ge: 0, le: 5, default: 0 }

  - route: /notes
    fields:
      text: { type: str, min_length: 1 }
    meta:
      methods: [GET]

  - route: /secrets
    fields:
      text: { type: str }
    meta:
      authentication: { backend: JWTAuthentication, permission: IsAuthenticated }

  - route: /mixed
    fields:
      text: { type: str }
    meta:
      authentication:
        backend: JWTAuthentication
      methods:
        GET:
          authentication: { permission: AllowAny }
        POST:
          authentication: { permission: IsAuthenticated }
        DELETE:
          authentication: { permission: IsAdminUser }
```

`tools/e2e/configs/12_yaml_async.yaml`:

```yaml
database:
  url: "@DB@"

mode: async

endpoints:
  - route: /asyncbooks
    fields:
      title: { type: str, min_length: 1 }
```

- [ ] **Step 7: Script** (tag `# e2e:`; this script starts two servers and does not use `apps/`)

Replace the "start the server" block with:

```bash
rm -f "$OUT/db.sqlite" "$OUT/async.sqlite"
sed "s|@DB@|sqlite:///$OUT/db.sqlite|" "$E2E/configs/12_yaml_serve.yaml" >"$OUT/config.yaml"
sed "s|@DB@|sqlite+aiosqlite:///$OUT/async.sqlite|" "$E2E/configs/12_yaml_async.yaml" >"$OUT/async.yaml"

serve() { # serve <config> <port> <log>
  LIGHTAPI_CONFIG=$1 LIGHTAPI_PORT=$2 LIGHTAPI_HOST=127.0.0.1 LIGHTAPI_JWT_SECRET=e2e-secret PYTHONPATH=$E2E \
    uv run --frozen --extra dev --directory "$ROOT" python -m lightapi serve >"$3" 2>&1 &
  echo $!
}
PID=$(serve "$OUT/config.yaml" "$PORT" "$OUT/server.log")
APORT=$((PORT + 1))
ABASE=http://127.0.0.1:$APORT
APID=$(serve "$OUT/async.yaml" "$APORT" "$OUT/async.server.log")
trap 'pkill -P $PID $APID 2>/dev/null; kill $PID $APID 2>/dev/null; wait $PID $APID 2>/dev/null' EXIT
for _ in $(seq 1 60); do
  curl -s -o /dev/null "$BASE/healthz" && curl -s -o /dev/null "$ABASE/healthz" && break
  sleep 0.25
done
for b in "$BASE" "$ABASE"; do
  if ! curl -s -o /dev/null "$b/healthz"; then echo "FAIL $NAME: server did not start on $b"; tail -20 "$OUT"/*.server.log; exit 1; fi
done
```

STEPS:

```bash
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
expect "create with defaults" 201 '.genre=="general" and .pages==null and .rating==0' -- -X POST -H "$JSON" -d '{"title":"Dune"}' "$BASE/books"
expect "min_length from yaml" 422 '' -- -X POST -H "$JSON" -d '{"title":""}' "$BASE/books"
expect "max_length from yaml" 422 '' -- -X POST -H "$JSON" -d "{\"title\":\"$(printf 'x%.0s' $(seq 1 41))\"}" "$BASE/books"
expect "le from yaml" 422 '' -- -X POST -H "$JSON" -d '{"title":"Bad","rating":9}' "$BASE/books"
expect "optional int" 201 '.pages==412' -- -X POST -H "$JSON" -d '{"title":"Foundation","genre":"scifi","pages":412}' "$BASE/books"
curl -s -o /dev/null -X POST -H "$JSON" -d '{"title":"Hyperion","genre":"scifi","pages":482}' "$BASE/books"
curl -s -o /dev/null -X POST -H "$JSON" -d '{"title":"Ulysses","genre":"fiction","pages":730}' "$BASE/books"
expect "defaults pagination" 200 '.count==4 and .pages==2 and (.results|length)==3' -- "$BASE/books"
expect "defaults filtering" 200 '.count==2' -- "$BASE/books?genre=scifi"
expect "defaults search" 200 '.count==1 and .results[0].title=="Ulysses"' -- "$BASE/books?search=uly"
expect "defaults ordering" 200 '.results[0].title=="Ulysses"' -- "$BASE/books?ordering=-pages"
expect "yaml get-only endpoint" 405 '.detail=="Method Not Allowed. Allowed: GET"' -- -X POST -H "$JSON" -d '{"text":"x"}' "$BASE/notes"
expect "yaml auth: no token" 401 '' -- "$BASE/secrets"
expect "yaml login validator by dotted path" 200 '(.token|type)=="string"' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
TOKEN=$(body .token)
expect "yaml auth: with token" 200 '.results==[]' -- -H "Authorization: Bearer $TOKEN" "$BASE/secrets"
expect "yaml per-method: anonymous get" 200 '' -- "$BASE/mixed"
expect "yaml per-method: anonymous post" 401 '' -- -X POST -H "$JSON" -d '{"text":"x"}' "$BASE/mixed"
expect "yaml per-method: user post" 201 '' -- -X POST -H "$JSON" -H "Authorization: Bearer $TOKEN" -d '{"text":"x"}' "$BASE/mixed"
expect "yaml per-method: user delete is 403" 403 '.detail=="Insufficient permissions"' -- -X DELETE -H "Authorization: Bearer $TOKEN" "$BASE/mixed/1"

expect "async document: healthz" 200 '.status=="ok"' -- "$ABASE/healthz"
expect "async document: create" 201 '.id==1' -- -X POST -H "$JSON" -d '{"title":"async"}' "$ABASE/asyncbooks"
expect "async document: list" 200 '(.results|length)==1' -- "$ABASE/asyncbooks"

# the CLI itself
uv run --frozen --extra dev --directory "$ROOT" python -m lightapi dance >"$OUT/dance.log" 2>&1
check "unknown command exits non-zero" $? -ne 0
env -u LIGHTAPI_CONFIG uv run --frozen --extra dev --directory "$ROOT" python -m lightapi serve >"$OUT/noconfig.log" 2>&1
check "missing LIGHTAPI_CONFIG exits non-zero" $? -ne 0
check "missing LIGHTAPI_CONFIG says so" "$(grep -ci 'LIGHTAPI_CONFIG' "$OUT/noconfig.log")" -ge 1
check "no traceback in the async server log" "$(grep -c Traceback "$OUT/async.server.log")" -eq 0
```

- [ ] **Step 8: Run alone**

Run: `tools/e2e/scenarios/12_yaml_serve.sh`
Expected: `27 passed, 0 failed`. If `python -m lightapi serve` without `LIGHTAPI_CONFIG`
exits 0 or prints a bare traceback, that is a CLI bug: fix in `lightapi/server.py` (a
`ConfigurationError` with the variable name, exit code 2) with a test in
`tests/test_server_command.py`, before the scenario's commit.

- [ ] **Step 9: Commit**

```bash
git add tools/e2e/configs/12_yaml_serve.yaml tools/e2e/configs/12_yaml_async.yaml tools/e2e/scenarios/12_yaml_serve.sh
git commit -m "test(e2e): lightapi serve on a YAML document, sync and async, defaults and per-method auth"
```

---

### Task 13: Scenario 13, rate limiting

**Files:**
- Create: `tools/e2e/scenarios/13_rate_limit.sh`, `tools/e2e/apps/13_rate_limit.py`

- [ ] **Step 1: App**

```python
"""e2e app for scenario 13: the login route is rate limited, CRUD routes are not."""

import os

from sqlalchemy import create_engine
from validators import check_login

from lightapi import Authentication, Field, IsAuthenticated, JWTAuthentication, LightApi, RateLimiter, RestEndpoint


class Secret(RestEndpoint):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e13_secrets"
        authentication = Authentication(backend=JWTAuthentication, permission=IsAuthenticated)


class Public(RestEndpoint):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e13_public"


def main() -> None:
    app = LightApi(
        engine=create_engine(os.environ["E2E_DB_URL"]),
        login_validator=check_login,
        rate_limiter=RateLimiter(requests_per_minute=3),
    )
    app.register({"/secrets": Secret, "/public": Public})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Script** (tag `# e2e:`, drop `e2e13_secrets, e2e13_public`)

```bash
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
expect "login 1" 200 '' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
expect "login 2 (bad) counts too" 401 '' -- -X POST -H "$JSON" -d '{"username":"user","password":"nope"}' "$BASE/auth/login"
expect "login 3" 200 '' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
expect "login 4 is limited" 429 '.detail=="Too many requests. Please try again later."' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
header "retry-after" '^retry-after: [0-9]+'
header "x-ratelimit-limit" '^x-ratelimit-limit: 3'
header "x-ratelimit-remaining" '^x-ratelimit-remaining: 0'
header "x-ratelimit-reset" '^x-ratelimit-reset: [0-9]+'
expect "login 5 still limited" 429 '' -- -X POST -H "$JSON" -d '{"username":"user","password":"password"}' "$BASE/auth/login"
for i in $(seq 1 10); do curl -s -o /dev/null -w '%{http_code}\n' "$BASE/public" >>"$OUT/public.codes"; done
check "crud route is not limited" "$(sort -u "$OUT/public.codes" | tr -d '\n')" = 200
```

Before the loop the script runs `: >"$OUT/public.codes"` so a rerun starts empty.

- [ ] **Step 3: Run alone**

Run: `tools/e2e/scenarios/13_rate_limit.sh`
Expected: `12 passed, 0 failed`.

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/13_rate_limit.sh tools/e2e/apps/13_rate_limit.py
git commit -m "test(e2e): the fourth login in a minute is 429 with the rate-limit headers"
```

---

### Task 14: Scenario 14, cache configured but Redis unreachable

**Files:**
- Create: `tools/e2e/scenarios/14_cache_fallback.sh`, `tools/e2e/apps/14_cache_fallback.py`

- [ ] **Step 1: App**

```python
"""e2e app for scenario 14: Meta.cache with no Redis behind it."""

import os

from sqlalchemy import create_engine

from lightapi import Cache, Field, LightApi, RestEndpoint


class Report(RestEndpoint):
    title: str = Field(min_length=1)

    class Meta:
        table = "e2e14_reports"
        cache = Cache(ttl=5)


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/reports": Report})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Script** (tag `# e2e:`, drop `e2e14_reports`; the start line adds `LIGHTAPI_REDIS_URL=redis://127.0.0.1:1/0` to the server's environment; the generic "no traceback" end check is replaced by the last two checks below)

```bash
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
check "startup warns that redis is unreachable" "$(grep -c 'not reachable at startup' "$OUT/server.log")" -ge 1
expect "get served from the database" 200 '.results==[]' -- "$BASE/reports"
expect "post" 201 '.id==1' -- -X POST -H "$JSON" -d '{"title":"q1"}' "$BASE/reports"
expect "get sees the new row (no stale cache)" 200 '(.results|length)==1' -- "$BASE/reports"
expect "get detail" 200 '.id==1' -- "$BASE/reports/1"
expect "delete" 204 '' -- -X DELETE "$BASE/reports/1"
expect "get after delete" 200 '.results==[]' -- "$BASE/reports"
check "cache misses are logged" "$(grep -cE 'Cache read failed' "$OUT/server.log")" -ge 1
check "every traceback belongs to a redis fallback" "$(grep -c Traceback "$OUT/server.log")" -eq "$(grep -cE 'Cache (read|write|invalidation) failed|Redis is not reachable' "$OUT/server.log")"
```

- [ ] **Step 3: Run alone**

Run: `tools/e2e/scenarios/14_cache_fallback.sh`
Expected: `10 passed, 0 failed`. The run must not be slow: the connect timeout is 1 s per
Redis call and a closed port fails at once, so the whole script takes under 5 s. A script
that takes 20 s means a call is waiting on the timeout; report it.

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/14_cache_fallback.sh tools/e2e/apps/14_cache_fallback.py
git commit -m "test(e2e): Meta.cache without Redis serves from the database and logs each miss"
```

---

### Task 15: Scenario 15, optimistic locking under concurrency (Postgres only)

**Files:**
- Create: `tools/e2e/scenarios/15_concurrency.sh`, `tools/e2e/apps/15_concurrency.py`

- [ ] **Step 1: App**

S2 with `class Counter(RestEndpoint)`: `label: str = Field(min_length=1)`,
`hits: int = Field(default=0)`, `table = "e2e15_counters"`, route `/counters`.

- [ ] **Step 2: Script** (tag `# e2e: pg-only`, drop `e2e15_counters`)

Right after `DB_URL=...` add:

```bash
case $DB_URL in postgresql*) ;; *) echo "== $NAME: 0 passed, 0 failed (needs E2E_DB_URL=postgresql+psycopg2://..., skipped)"; exit 0 ;; esac
```

STEPS:

```bash
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
```

- [ ] **Step 3: Run through run_all**

Run: `tools/e2e/run_all.sh concurrency`
Expected: `ok 15_concurrency[pg] 9 passed, 0 failed` and no SQLite line. A `500` in
`codes` means the conflict path raised on Postgres (deadlock or a rollback that was not
done): read the server log and fix in `lightapi/repository.py` with a unit test before
the commit.

- [ ] **Step 4: Commit**

```bash
git add tools/e2e/scenarios/15_concurrency.sh tools/e2e/apps/15_concurrency.py
git commit -m "test(e2e): ten parallel writers on Postgres, one 200 and nine 409"
```

---

### Task 16: Fix the unique-violation 500, then scenario 17 (Field options)

**Files:**
- Modify: `lightapi/repository.py` (`add`, `update`, new `ConstraintViolation`), `lightapi/constants.py` (`ApiError.CONSTRAINT_VIOLATION`), `lightapi/rest.py` (`_API_ERRORS`, `_create`, `_update`)
- Test: `tests/test_constraints.py` (new)
- Create: `tools/e2e/scenarios/17_field_options.sh`, `tools/e2e/apps/17_field_options.py`

**Interfaces:**
- Produces: `lightapi.repository.ConstraintViolation(Exception)`; `ApiError.CONSTRAINT_VIOLATION = (HTTPStatus.CONFLICT, "constraint violation")`; POST/PUT/PATCH answer `409 {"detail": "constraint violation"}` on `IntegrityError`.

- [ ] **Step 1: Failing tests**

`tests/test_constraints.py`:

```python
"""A database constraint violation is a 409, not a 500, on every write path."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
from lightapi.fields import Field as LField


class Account(RestEndpoint):
    email: str = LField(min_length=1, unique=True)
    name: str = LField(default="")

    class Meta:
        table = "constraint_accounts"


def _memory_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def client():
    app = LightApi(engine=_memory_engine())
    app.register({"/accounts": Account})
    with TestClient(app.build_app()) as c:
        yield c


def test_duplicate_unique_value_on_post_answers_409(client):
    assert client.post("/accounts", json={"email": "a@x"}).status_code == 201

    duplicate = client.post("/accounts", json={"email": "a@x"})

    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "constraint violation"}
    assert len(client.get("/accounts").json()["results"]) == 1


def test_update_to_duplicate_unique_value_answers_409(client):
    client.post("/accounts", json={"email": "a@x"})
    second = client.post("/accounts", json={"email": "b@x"}).json()

    collide = client.put(
        f"/accounts/{second['id']}", json={"email": "a@x", "name": "", "version": 1}
    )

    assert collide.status_code == 409
    assert collide.json() == {"detail": "constraint violation"}
    assert client.get(f"/accounts/{second['id']}").json()["email"] == "b@x"


def test_the_session_is_usable_after_the_409(client):
    client.post("/accounts", json={"email": "a@x"})
    client.post("/accounts", json={"email": "a@x"})

    assert client.post("/accounts", json={"email": "c@x"}).status_code == 201


async def test_duplicate_on_the_async_path_answers_409():
    class AsyncAccount(RestEndpoint):
        email: str = LField(min_length=1, unique=True)

        class Meta:
            table = "constraint_async_accounts"

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = LightApi(engine=engine, mode="async")
    app.register({"/asyncaccounts": AsyncAccount})
    with TestClient(app.build_app()) as client:
        assert client.post("/asyncaccounts", json={"email": "a@x"}).status_code == 201
        assert client.post("/asyncaccounts", json={"email": "a@x"}).status_code == 409
    await engine.dispose()
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run --frozen --extra dev pytest tests/test_constraints.py -q -p no:cacheprovider`
Expected: 4 failed with `sqlalchemy.exc.IntegrityError` (or a 500 status).

- [ ] **Step 3: Implement**

`lightapi/repository.py`: import `from sqlalchemy.exc import IntegrityError`, add after
`VersionConflict`:

```python
class ConstraintViolation(Exception):
    """The database refused the write: a unique, foreign-key or check constraint."""
```

In `add()`:

```python
        self._session.add(row)
        try:
            self._session.flush()  # executes INSERT, populates auto-increment id
        except IntegrityError as exc:
            self._session.rollback()
            raise ConstraintViolation(str(exc.orig)) from exc
        self._session.refresh(row)  # re-loads DB-generated columns
        return row
```

In `update()` wrap the `execute(update(...))`:

```python
        try:
            result = self._session.execute(
                update(model)
                .where(model.id == pk, model.version == expected_version)
                .values(**values, version=expected_version + 1, updated_at=self.utcnow())
            )
        except IntegrityError as exc:
            self._session.rollback()
            raise ConstraintViolation(str(exc.orig)) from exc
```

`lightapi/constants.py`, in `ApiError`, after `VERSION_CONFLICT`:

```python
    CONSTRAINT_VIOLATION = (HTTPStatus.CONFLICT, "constraint violation")
```

`lightapi/rest.py`: import `ConstraintViolation` beside `RowNotFound, VersionConflict`;
add `ConstraintViolation: ApiError.CONSTRAINT_VIOLATION` to `_API_ERRORS`; in `_create`
wrap the add:

```python
        try:
            row = self._repository(session).add(validated.model_dump())
        except ConstraintViolation as exc:
            return _API_ERRORS[type(exc)].response()
```

and in `_update` extend the except tuple to
`except (RowNotFound, VersionConflict, ConstraintViolation) as exc:`.

- [ ] **Step 4: Run the tests and the gates**

Run: `uv run --frozen --extra dev pytest tests/ -q -p no:cacheprovider && uv run --frozen --extra dev ruff check lightapi tests && uv run --frozen --extra dev ruff format --check lightapi tests && uv run --frozen --extra dev mypy lightapi`
Expected: 596 passed, everything clean. Also update the README "Error responses" table
with a row `| Constraint violation (unique, foreign key) | \`409\` | \`{"detail": "constraint violation"}\` |`
and the same row in `docs/api-reference/rest.md`; `mkdocs build --strict` stays green.

- [ ] **Step 5: CHANGELOG, audit doc, commit**

CHANGELOG `### Fixed`:

```
- **A database constraint violation is a 409**: a duplicate on a `unique=True` column (or
  any `IntegrityError`) on POST, PUT or PATCH answers `409 {"detail": "constraint violation"}`
  and leaves the session usable. It was an unhandled 500.
```

`docs/audit.md`: add row `B1-019 | B1 | lightapi/repository.py | IntegrityError unhandled: duplicate unique value is a 500 | corrigido: 409 "constraint violation" | corrigido | <hash>` and bump the B1 line of the summary table.

```bash
git add lightapi/repository.py lightapi/constants.py lightapi/rest.py tests/test_constraints.py README.md docs/api-reference/rest.md CHANGELOG.md docs/audit.md
git commit -m "fix: a constraint violation answers 409 instead of an unhandled 500

A duplicate on a unique=True column raised IntegrityError out of
Repository.add()/update() and the request died with a 500 and a
traceback. The Repository rolls back and raises ConstraintViolation;
the endpoint maps it to 409 {\"detail\": \"constraint violation\"} on
POST, PUT and PATCH, sync and async."
```

- [ ] **Step 6: App for scenario 17**

```python
"""e2e app for scenario 17: Field column options and the unique-violation path."""

import os
from decimal import Decimal

from sqlalchemy import create_engine

from lightapi import Field, LightApi, RestEndpoint


class Category(RestEndpoint):
    name: str = Field(min_length=1)

    class Meta:
        table = "e2e17_categories"


class Product(RestEndpoint):
    sku: str = Field(min_length=1, unique=True)
    name: str = Field(min_length=1, index=True)
    price: Decimal = Field(decimal_places=2)
    internal_note: str = Field(default="", exclude=True)
    category_id: int | None = Field(default=None, foreign_key="e2e17_categories.id")

    class Meta:
        table = "e2e17_products"


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/categories": Category, "/products": Product})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Script** (tag `# e2e: pg`, drop `e2e17_products, e2e17_categories` in that order)

```bash
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
case $DB_URL in
  sqlite*) SCHEMA=$(sqlite3 "$OUT/db.sqlite" '.schema e2e17_products' ; sqlite3 "$OUT/db.sqlite" '.indexes e2e17_products') ;;
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
expect "second product" 201 '.id==2' -- -X POST -H "$JSON" -d '{"sku":"B-2","name":"Bolt","price":"0.25"}' "$BASE/products"
expect "put to duplicate sku" 409 '.detail=="constraint violation"' -- -X PUT -H "$JSON" -d '{"sku":"A-1","name":"Bolt","price":"0.25","version":1}' "$BASE/products/2"
expect "row untouched after the 409" 200 '.sku=="B-2" and .version==1' -- "$BASE/products/2"
expect "writes still work after the 409" 201 '.id==3' -- -X POST -H "$JSON" -d '{"sku":"C-3","name":"Cog","price":"3.75"}' "$BASE/products"
expect "decimal with more places is rounded or rejected, never 500" 201 '' -- -X POST -H "$JSON" -d '{"sku":"D-4","name":"Dial","price":"1.999"}' "$BASE/products"
```

The last step accepts 201 because SQLite stores NUMERIC loosely; on Postgres the
`numeric(10,2)` column rounds. If either answers 500, the Decimal path has a bug to fix
(`tests/test_schema.py`) before the commit.

- [ ] **Step 8: Run alone and through run_all**

Run: `tools/e2e/scenarios/17_field_options.sh && tools/e2e/run_all.sh field_options`
Expected: `15 passed, 0 failed` on SQLite and `[pg]`. On Postgres the "duplicate sku"
step is the one that proves the fix end to end with a real unique index.

- [ ] **Step 9: Commit**

```bash
git add tools/e2e/scenarios/17_field_options.sh tools/e2e/apps/17_field_options.py
git commit -m "test(e2e): Field column options reach the schema; a duplicate unique value is 409"
```

---

### Task 17: Fix B20 (HEALTHCHECK path), then scenario 16 (the container image)

**Files:**
- Modify: `Dockerfile` (HEALTHCHECK URL)
- Create: `tools/e2e/Dockerfile.local`, `tools/e2e/configs/16_docker.yaml`, `tools/e2e/scenarios/16_docker.sh`

- [ ] **Step 1: Fix the HEALTHCHECK**

In `Dockerfile` replace the comment and the URL:

```
# Health check against the liveness route the app always registers.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
import os; \
url='http://127.0.0.1:'+os.environ.get('LIGHTAPI_PORT','8000')+'/healthz'; \
sys.exit(0 if urllib.request.urlopen(url, timeout=2).status else 1)" \
    || exit 1
```

CHANGELOG `### Fixed`:

```
- **The container HEALTHCHECK probes `/healthz`**: it hit `/`, which is a 404, so
  `docker inspect` reported every healthy container as unhealthy.
```

`docs/audit.md`: add row `B14-009 | B14 | Dockerfile | HEALTHCHECK probes / (404) so the container is always unhealthy (B20) | corrigido: /healthz | corrigido | <hash>`.

```bash
git add Dockerfile CHANGELOG.md docs/audit.md
git commit -m "fix: the container HEALTHCHECK probes /healthz, not /

/ is a 404 on every LightAPI app, so docker reported the image as
unhealthy no matter what. /healthz is the route the app registers for
exactly this."
```

- [ ] **Step 2: A Dockerfile that installs this checkout**

The repository `Dockerfile` installs the published wheel, so it cannot prove this branch.
`tools/e2e/Dockerfile.local` builds the same image from `dist/`:

```dockerfile
# syntax=docker/dockerfile:1.7
# The repository Dockerfile with one difference: it installs the wheel built from this
# checkout (uv build -> dist/) instead of the published release. Used by
# tools/e2e/scenarios/16_docker.sh only.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    LIGHTAPI_CONFIG=/app/lightapi.yaml \
    LIGHTAPI_HOST=0.0.0.0 \
    LIGHTAPI_PORT=8000 \
    LIGHTAPI_LOG_LEVEL=info

WORKDIR /app

COPY dist/*.whl /tmp/dist/
RUN pip install "$(ls /tmp/dist/*.whl)[async]" psycopg2-binary && rm -rf /tmp/dist /root/.cache

COPY docker/entrypoint.py /app/entrypoint.py

RUN groupadd --system --gid 1001 lightapi \
 && useradd  --system --uid 1001 --gid lightapi --home-dir /app --no-create-home lightapi \
 && chown -R lightapi:lightapi /app
USER lightapi

EXPOSE 8000

HEALTHCHECK --interval=2s --timeout=2s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; \
import os; \
url='http://127.0.0.1:'+os.environ.get('LIGHTAPI_PORT','8000')+'/healthz'; \
sys.exit(0 if urllib.request.urlopen(url, timeout=2).status else 1)" \
    || exit 1

ENTRYPOINT ["python", "/app/entrypoint.py"]
```

The interval is 2 s here (30 s in the real image) so the scenario can read `healthy`
within seconds. `psycopg2-binary` is in the published image too.

- [ ] **Step 3: The document the container serves**

`tools/e2e/configs/16_docker.yaml`:

```yaml
database:
  url: "sqlite:////tmp/e2e.sqlite"

endpoints:
  - route: /books
    fields:
      title: { type: str, min_length: 1 }
```

- [ ] **Step 4: Script** (tag `# e2e: docker`; no `apps/` server)

Replace the "start the server" block with:

```bash
IMAGE=lightapi-e2e
CONTAINER=lightapi-e2e-app
PORT=${E2E_PORT:-18199}
BASE=http://127.0.0.1:$PORT
rm -rf "$ROOT/dist"
(cd "$ROOT" && uv build >"$OUT/build.log" 2>&1) || { echo "FAIL $NAME: uv build failed"; tail -20 "$OUT/build.log"; exit 1; }
docker build -q -t $IMAGE -f "$E2E/Dockerfile.local" "$ROOT" >"$OUT/docker-build.log" 2>&1 || { echo "FAIL $NAME: docker build failed"; tail -30 "$OUT/docker-build.log"; exit 1; }
docker rm -f $CONTAINER >/dev/null 2>&1 || true
docker run -d --rm --name $CONTAINER -p 127.0.0.1:$PORT:8000 \
  -v "$E2E/configs/16_docker.yaml:/app/lightapi.yaml:ro" $IMAGE >/dev/null
trap 'docker logs $CONTAINER >"$OUT/server.log" 2>&1; docker rm -f $CONTAINER >/dev/null 2>&1' EXIT
for _ in $(seq 1 60); do
  curl -s -o /dev/null "$BASE/healthz" && break
  sleep 0.5
done
if ! curl -s -o /dev/null "$BASE/healthz"; then echo "FAIL $NAME: container did not answer"; docker logs $CONTAINER | tail -20; exit 1; fi
```

STEPS:

```bash
expect "healthz" 200 '.status=="ok"' -- "$BASE/healthz"
expect "create" 201 '.id==1' -- -X POST -H "$JSON" -d '{"title":"in a container"}' "$BASE/books"
expect "list" 200 '(.results|length)==1' -- "$BASE/books"
expect "validation" 422 '' -- -X POST -H "$JSON" -d '{"title":""}' "$BASE/books"
for _ in $(seq 1 20); do [ "$(docker inspect -f '{{.State.Health.Status}}' $CONTAINER)" = healthy ] && break; sleep 1; done
check "docker reports healthy" "$(docker inspect -f '{{.State.Health.Status}}' $CONTAINER)" = healthy
check "runs as the non-root user" "$(docker exec $CONTAINER id -u)" = 1001
```

The end block keeps the `Traceback` check (the trap writes `docker logs` to `server.log`
before the check runs, so move the `docker logs` line to just before the final `check`).

- [ ] **Step 5: Run it**

Run: `E2E_DOCKER=1 tools/e2e/run_all.sh docker`
Expected: `ok 16_docker 7 passed, 0 failed` (two to three minutes for the first build).

- [ ] **Step 6: Commit**

```bash
git add tools/e2e/Dockerfile.local tools/e2e/configs/16_docker.yaml tools/e2e/scenarios/16_docker.sh
git commit -m "test(e2e): the container image serves the mounted YAML and reports healthy"
```

---

### Task 18: Full runs, README gaps section, final report

**Files:**
- Modify: `tools/e2e/README.md` (only if a gap had to stay), `docs/audit.md` (Phase 3 note)

- [ ] **Step 1: Both Pythons, twice**

```bash
tools/e2e/run_all.sh | tee tools/e2e/.out/run-313-1.txt
tools/e2e/run_all.sh | tee tools/e2e/.out/run-313-2.txt
```

Expected: identical summaries, exit 0, under 3 minutes each. Then the 3.10 server
interpreter: the scripts call `uv run --frozen --extra dev`; run them once more with
`UV_PYTHON=3.10` exported, which makes every `uv run` in the scripts use 3.10
(`UV_PYTHON=3.10 tools/e2e/run_all.sh | tee tools/e2e/.out/run-310.txt`); expected exit 0.
If `uv` refuses `--frozen` with another interpreter, add `UV_PROJECT_ENVIRONMENT=$ROOT/.venv310`
to the same command so it builds a second environment instead of touching `.venv`.

- [ ] **Step 2: Each script alone**

```bash
for s in tools/e2e/scenarios/0*.sh tools/e2e/scenarios/1[0-5]*.sh tools/e2e/scenarios/17*.sh; do "$s" >/dev/null && echo "ok $s" || echo "FAIL $s"; done
```

Expected: every line `ok` (15 is `ok` because it skips without Postgres).

- [ ] **Step 3: Audit doc and README**

Append to `docs/audit.md` Phase 3 a short "End-to-end curl suite" paragraph: the
scenario count, the step total from `run-313-1.txt`, the Python versions, and the fixes it
forced (B6-001, B20, the constraint 409, the docs text). If any `KNOWN` line exists in the
summary, name it under "Known gaps" in `tools/e2e/README.md` with the reason; otherwise
leave "Known gaps: none."

```bash
git add docs/audit.md tools/e2e/README.md
git commit -m "docs(e2e): record the full run and what it forced"
```

- [ ] **Step 4: Report**

The final message to Henry (Portuguese, plain): the branch and commit count, the two run
summaries verbatim (3.13 and 3.10), the fixes made with their commits, anything left as a
gap, and the one command to rerun everything.
