---
title: Docker Deployment
description: Run a fully-configured LightAPI server in seconds with the official iklobato/lightapi image
---

# Docker Deployment

The official image bundles LightAPI, its async extras, and PostgreSQL drivers.
Mount a YAML config and a database URL — no Python code or build step required.

```
iklobato/lightapi:latest
iklobato/lightapi:<version>      # e.g. 0.1.21
iklobato/lightapi:master         # rolling head of master
```

The image is multi-arch (`linux/amd64`, `linux/arm64`) and is built from the
[`Dockerfile`](https://github.com/iklobato/LightAPI/blob/master/Dockerfile)
at the repository root.

## Quickstart

1. Write a config file (`lightapi.yaml`):

    ```yaml
    database:
      url: "${DATABASE_URL}"

    endpoints:
      - route: /books
        fields:
          title:  { type: str, min_length: 1, max_length: 200 }
          author: { type: str, min_length: 1 }
          year:   { type: int, optional: true }
        meta:
          methods: [GET, POST, PUT, PATCH, DELETE]
          pagination:
            style: page_number
            page_size: 25
    ```

2. Start the container:

    ```bash
    docker run --rm -p 8000:8000 \
        -v "$(pwd)/lightapi.yaml:/app/lightapi.yaml:ro" \
        -e DATABASE_URL=sqlite:////app/data.db \
        iklobato/lightapi:latest
    ```

3. Use the API:

    ```bash
    curl -X POST http://localhost:8000/books \
         -H 'Content-Type: application/json' \
         -d '{"title": "Clean Code", "author": "Martin", "year": 2008}'
    curl http://localhost:8000/books
    ```

That's the whole flow — no `pip install`, no manual `LightApi(...)`. The
container reads `/app/lightapi.yaml` on start, builds the app, and starts
uvicorn on port 8000.

## Configuration surface

### Mount points

| Path | Purpose |
|---|---|
| `/app/lightapi.yaml` | Your endpoint config (the only required mount). |
| `/app/data.db` | Suggested location for an on-disk SQLite database (mount a volume to persist it). |

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `LIGHTAPI_CONFIG` | `/app/lightapi.yaml` | Override the config path. |
| `LIGHTAPI_HOST` | `0.0.0.0` | Uvicorn bind address. |
| `LIGHTAPI_PORT` | `8000` | Uvicorn port. |
| `LIGHTAPI_LOG_LEVEL` | `info` | `debug`, `info`, `warning`, `error`. |
| `DATABASE_URL` | — | Substituted into `${DATABASE_URL}` in your YAML. |
| `LIGHTAPI_JWT_SECRET` | — | Required when your config enables JWT authentication. |
| `LIGHTAPI_REDIS_URL` | `redis://localhost:6379/0` | Used when `Cache(...)` is configured. |

Any other `${VAR}` placeholder in the YAML is resolved against the
container environment at startup.

## Examples

### SQLite + persistent volume

```bash
docker volume create lightapi-data
docker run -d --name lightapi \
    -p 8000:8000 \
    -v "$(pwd)/lightapi.yaml:/app/lightapi.yaml:ro" \
    -v lightapi-data:/app \
    -e DATABASE_URL=sqlite:////app/data.db \
    iklobato/lightapi:latest
```

### PostgreSQL via docker compose

```yaml
# docker-compose.yml
services:
  api:
    image: iklobato/lightapi:latest
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://api:apipass@db:5432/api
      LIGHTAPI_JWT_SECRET: replace-me-in-production
    volumes:
      - ./lightapi.yaml:/app/lightapi.yaml:ro
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: api
      POSTGRES_PASSWORD: apipass
      POSTGRES_DB: api
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "api"]
      interval: 5s
      retries: 5
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

```bash
docker compose up -d
```

When `database.url` resolves to a `postgresql+asyncpg://...` URL, LightAPI
auto-detects the async engine and serves every endpoint asynchronously.

### Redis cache

```bash
docker run --rm -p 8000:8000 \
    -v "$(pwd)/lightapi.yaml:/app/lightapi.yaml:ro" \
    -e DATABASE_URL=sqlite:////app/data.db \
    -e LIGHTAPI_REDIS_URL=redis://redis:6379/0 \
    --network my-net \
    iklobato/lightapi:latest
```

If Redis is unreachable, LightAPI logs a `RuntimeWarning` once at startup
and falls back to serving from the database — your endpoints keep working.

### JWT authentication

```yaml
# lightapi.yaml
database:
  url: "${DATABASE_URL}"

defaults:
  authentication:
    backend: JWTAuthentication
    permission: IsAuthenticated

endpoints:
  - route: /books
    fields:
      title:  { type: str }
      author: { type: str }
    meta:
      methods: [GET, POST, PUT, DELETE]

auth:
  login_validator: myapp.auth.validate_login
```

```bash
docker run --rm -p 8000:8000 \
    -v "$(pwd)/lightapi.yaml:/app/lightapi.yaml:ro" \
    -v "$(pwd)/myapp:/app/myapp:ro" \
    -e PYTHONPATH=/app \
    -e DATABASE_URL=sqlite:////app/data.db \
    -e LIGHTAPI_JWT_SECRET=replace-me \
    iklobato/lightapi:latest
```

`POST /auth/login` is auto-registered because at least one endpoint declares
`JWTAuthentication`. See
[Authentication](../advanced/authentication.md) for the credential-validator
contract.

## Custom image

If you need extra Python dependencies (a custom `login_validator`, custom
middleware, etc.), extend the published image:

```dockerfile
FROM iklobato/lightapi:0.1.21

# Add your own modules — they must be importable from the YAML's dotted paths.
COPY ./myapp /app/myapp
ENV PYTHONPATH=/app

# Add any extra Python deps.
RUN pip install --no-cache-dir requests redis
```

## Image build internals

The Dockerfile uses `python:3.12-slim`, installs LightAPI with the `async`
extra plus PostgreSQL drivers, drops privileges to a non-root `lightapi`
user, and ships a small entrypoint (`docker/entrypoint.py`) that:

1. Resolves the config path (`LIGHTAPI_CONFIG`, default `/app/lightapi.yaml`).
2. Calls `LightApi.from_config(path)`.
3. Calls `app.build_app()` and runs uvicorn with `proxy_headers=True` and
   `forwarded_allow_ips="*"` so reverse-proxy headers (`X-Forwarded-For`,
   `X-Forwarded-Proto`) are honoured.

To build the image locally:

```bash
git clone https://github.com/iklobato/LightAPI.git
cd LightAPI
docker build --build-arg LIGHTAPI_VERSION=0.1.21 -t lightapi:local .
```

## Publishing pipeline

`master` pushes and every `v*.*.*` tag trigger
`.github/workflows/docker-publish.yml`, which builds the multi-arch image
and pushes to Docker Hub. The workflow needs two repository secrets:

| Secret | Value |
|---|---|
| `DOCKERHUB_USERNAME` | Your Docker Hub username (`iklobato`). |
| `DOCKERHUB_TOKEN` | A Docker Hub access token with read+write scope on `iklobato/lightapi`. |

Tag schedule:

| Event | Tags pushed |
|---|---|
| Push of `v0.1.21` | `iklobato/lightapi:0.1.21`, `:0.1`, `:latest` |
| Push to `master` | `iklobato/lightapi:master` |
| Manual `workflow_dispatch` | `iklobato/lightapi:manual-<run-number>` |
