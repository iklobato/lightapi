# End-to-end curl suite

Real server process, real `curl`, throwaway databases. `tools/e2e/run_all.sh` runs every
`scenarios/*.sh` against a SQLite file, then again against a Postgres container
(`lightapi-e2e-pg`, 127.0.0.1:55432) for the scenarios tagged `pg`. Exit 0 only when every
step of every run passed.

    tools/e2e/run_all.sh                       # everything (needs docker for the [pg] runs)
    tools/e2e/run_all.sh auth                  # scenarios whose name contains "auth"
    E2E_NO_DOCKER=1 tools/e2e/run_all.sh       # skip the [pg] runs instead of failing them
    E2E_DOCKER=1 tools/e2e/run_all.sh docker   # build and probe the container image
    tools/e2e/scenarios/04_auth_jwt.sh         # one scenario alone, SQLite, port 18100

Needs: jq, curl, uv, sqlite3, psql, docker. The [pg] runs also need both Postgres drivers in
the uv environment: the scripts run `uv run --frozen --extra dev --extra async`, which gives
asyncpg from the lock; psycopg2 is in no manifest, so install it once with
`uv pip install psycopg2-binary`. `run_all.sh` checks both before the first run. Logs,
response bodies and databases land in `tools/e2e/.out/<scenario>/` (gitignored).

To run the whole suite on the other supported interpreter, point uv at a second
environment (built from the same lock) and install the driver there too:

    uv pip install --python .venv310/bin/python psycopg2-binary   # after the first run created it
    UV_PYTHON=3.10 UV_PROJECT_ENVIRONMENT=$PWD/.venv310 tools/e2e/run_all.sh

Each script is self-contained: it starts its app from `apps/<name>.py` (or
`python -m lightapi serve` on `configs/<name>.yaml`), waits for `/healthz`, runs its steps
with an inline `expect <step> <status> <jq filter> -- <curl args>`, and kills the server on
exit. Scripts share no helper file on purpose.

Environment the scripts read: `E2E_PORT` (default 18100), `E2E_DB_URL` (default a SQLite
file under `.out/`), `E2E_PSQL` (set by `run_all.sh` for the [pg] runs).

Known gaps: none. A step that pins a gap that cannot be fixed here would say so in this
section.
