# Plan: package LightAPI as a Helm chart (zero-CRUD-code deploys)

## Goal

A team that needs a CRUD API over an existing database writes only a
`values.yaml` (DB connection + the endpoint/table definitions) and runs
`helm install`. No Python, no CRUD code, no per-project image build.

## Why this is small

LightAPI already does the hard part. `LightApi.from_config(path)` builds a full
CRUD API from a declarative YAML file, supports `${VAR}` env substitution in the
DB URL, and can `reflect` existing tables. So the chart never generates CRUD:
it only has to (1) hand LightAPI that YAML, (2) inject secrets, (3) run the
process, (4) expose it. The YAML the framework already parses *is* the chart's
config surface.

## What is actually missing (three gaps)

Confirmed by reading the repo: no server entrypoint that reads a config path
from env, no health route, no Dockerfile/chart.

### 1. A first-class serve entrypoint (belongs in the package, not the chart)

Add a `lightapi serve` console command (SOLID: one object owns "boot from
environment"). It replaces the ad-hoc `run_server.py`.

- New: `lightapi/server.py` with a `ServerCommand` class. It reads
  `LIGHTAPI_CONFIG` (config path), `LIGHTAPI_HOST`, `LIGHTAPI_PORT` and calls
  `LightApi.from_config(path).run(host, port)`. Env parsing is the object's one
  responsibility; it delegates building to `from_config` and serving to `run`.
- `lightapi/__main__.py`: `ServerCommand.from_env().execute()` so
  `python -m lightapi` works too.
- `pyproject.toml`: `[project.scripts] lightapi = "lightapi.server:main"`.
- `main()` is a thin adapter over `ServerCommand` (no logic in the free
  function; it constructs the object and calls it).

### 2. A `/healthz` route in the framework (belongs in `LightApi`)

The probe must not depend on a business endpoint. Add `/healthz` in
`LightApi.build_app()` / `run()` where the Starlette route list is assembled
(same spot the auth routes are inserted, `lightapi.py:376`). A tiny
`HealthCheck` handler returns `{"status": "ok"}` (200). Optionally it pings the
DB engine; start with process-only (liveness) and add a DB ping variant for
readiness later.

### 3. Container image + chart (the packaging itself)

Single generic published image; every deploy reuses it and only swaps
`values.yaml`.

## Deliverables

```
Dockerfile                     # generic image: installs lightapi, ENTRYPOINT ["lightapi","serve"]
lightapi/server.py             # ServerCommand (env -> from_config -> run)
lightapi/__main__.py           # python -m lightapi
charts/lightapi/
  Chart.yaml                   # appVersion pinned to the image tag
  values.yaml                  # documented defaults
  templates/
    _helpers.tpl               # names/labels
    configmap.yaml             # renders .Values.config (the lightapi.yaml) verbatim
    secret.yaml                # DATABASE_URL, LIGHTAPI_JWT_SECRET (+ existingSecret opt-out)
    deployment.yaml            # mounts config, env from secret, /healthz probes
    service.yaml
    ingress.yaml               # optional (.Values.ingress.enabled)
    hpa.yaml                   # optional
    serviceaccount.yaml
    NOTES.txt                  # how to reach the API after install
```

## values.yaml shape (the entire developer-facing surface)

```yaml
image:
  repository: iklobato/lightapi
  tag: ""            # defaults to Chart.appVersion

replicaCount: 2

# Connection to a database that already exists (chart does NOT manage the DB).
database:
  # either a full URL...
  urlSecret:
    existingSecret: ""      # name of a Secret holding DATABASE_URL
    key: DATABASE_URL
  # ...or let the chart create the Secret from this value (dev only):
  url: ""                   # e.g. postgresql://user:pass@host:5432/app

jwt:
  existingSecret: ""
  secret: ""                # LIGHTAPI_JWT_SECRET (required only if endpoints use JWT)

redis:
  url: ""                   # LIGHTAPI_REDIS_URL, only if an endpoint sets cache

# This block is copied verbatim into a ConfigMap and passed to from_config().
# It is exactly the declarative lightapi.yaml the framework already parses.
config:
  database:
    url: "${DATABASE_URL}"        # resolved from the Secret at runtime
  defaults:
    pagination: { style: page_number, page_size: 20 }
  endpoints:
    - route: /products
      fields:
        name:     { type: str, max_length: 200 }
        price:    { type: float }
        in_stock: { type: bool, default: true }
      meta:
        methods: [GET, POST, PUT, DELETE]
        filtering: { fields: [in_stock], ordering: [price] }
    # To wrap an existing table instead of declaring fields:
    - route: /legacy_users
      reflect: true
      meta: { methods: [GET] }

ingress:
  enabled: false
  className: ""
  hosts: []
autoscaling:
  enabled: false
resources: {}
```

## How the pieces wire at runtime

1. `configmap.yaml` writes `.Values.config` to `/etc/lightapi/lightapi.yaml`.
2. `deployment.yaml` sets `LIGHTAPI_CONFIG=/etc/lightapi/lightapi.yaml` and pulls
   `DATABASE_URL` / `LIGHTAPI_JWT_SECRET` / `LIGHTAPI_REDIS_URL` from the Secret.
3. `ENTRYPOINT lightapi serve` -> `ServerCommand.from_env()` -> `from_config()`
   parses the mounted YAML, `${DATABASE_URL}` is substituted from env, tables are
   created/reflected, uvicorn serves on `LIGHTAPI_PORT` (8000).
4. Liveness/readiness probes hit `/healthz`.

## Developer workflow (the payoff)

```bash
helm install shop charts/lightapi \
  -f my-values.yaml            # my-values.yaml = DB url + the endpoints block
```
No CRUD code written. Adding a table = add an entry under `config.endpoints` and
`helm upgrade`.

## Decisions locked

- Database: external (chart is stateless; no bundled Postgres).
- Health: real `/healthz` added to the framework.
- Image: one generic published image, config injected via values.

## Out of scope (add when needed)

- Bundled Postgres/Redis subcharts (dev-only convenience).
- DB migrations beyond `create_all` (LightAPI creates missing tables; it does not
  run schema migrations).
- Multi-tenant / per-endpoint image splitting.

## Build order

1. `ServerCommand` + `__main__` + `[project.scripts]` (self-check: `python -m
   lightapi` boots a demo config).
2. `/healthz` route + one test.
3. Dockerfile; build and run the image locally against a Postgres.
4. Chart templates; `helm template` + `helm lint`; `helm install` on kind/minikube.
```
