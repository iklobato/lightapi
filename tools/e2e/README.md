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
