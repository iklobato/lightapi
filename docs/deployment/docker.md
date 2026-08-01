---
title: Docker Deployment
---

LightAPI ships a generic image whose entry point is `lightapi serve`. That
command reads `LIGHTAPI_CONFIG` (the declarative YAML), `LIGHTAPI_HOST`, and
`LIGHTAPI_PORT` from the environment, so the same image serves any API: you
inject the config at run time instead of baking it in.

## Dockerfile

The repository root has a ready-to-use `Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /src
COPY . /src
# Framework + DB drivers a deployed API may need (sync + async Postgres).
RUN pip install --no-cache-dir ".[async]" psycopg2-binary
ENV LIGHTAPI_CONFIG=/etc/lightapi/lightapi.yaml \
    LIGHTAPI_HOST=0.0.0.0 \
    LIGHTAPI_PORT=8000
EXPOSE 8000
ENTRYPOINT ["lightapi", "serve"]
```

Build it:

```bash
docker build -t youracct/lightapi:0.1.21 .
```

## docker-compose.yml

Mount your declarative config and point `DATABASE_URL` at the database. The
config references `${DATABASE_URL}`, which LightAPI substitutes at startup.

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://postgres:pass@db:5432/mydb
      # LIGHTAPI_JWT_SECRET / LIGHTAPI_REDIS_URL only if used by an endpoint
    volumes:
      - ./lightapi.yaml:/etc/lightapi/lightapi.yaml:ro
    depends_on: [db]
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: mydb
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: pass
```

`lightapi.yaml` next to the compose file:

```yaml
database:
  url: "${DATABASE_URL}"
endpoints:
  - route: /products
    fields:
      name:  { type: str, max_length: 200 }
      price: { type: float }
    meta:
      methods: [GET, POST, PUT, DELETE]
      authentication: { permission: AllowAny }
```

### Building and running

```bash
docker compose up --build
curl http://127.0.0.1:8000/healthz
```

For Kubernetes, see the [Kubernetes (Helm)](helm.md) guide.
