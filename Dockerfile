# Generic LightAPI runtime image.
#
# Config is injected at deploy time via LIGHTAPI_CONFIG (a mounted declarative
# YAML file), so the same image serves any API — no per-project build.
FROM python:3.12-slim

WORKDIR /src
COPY . /src

# Framework + DB drivers a deployed API may need: psycopg2 (sync Postgres, the
# driver create_engine uses for postgresql://) and the async extra (asyncpg).
RUN pip install --no-cache-dir ".[async]" psycopg2-binary

ENV LIGHTAPI_CONFIG=/etc/lightapi/lightapi.yaml \
    LIGHTAPI_HOST=0.0.0.0 \
    LIGHTAPI_PORT=8000

EXPOSE 8000
ENTRYPOINT ["lightapi", "serve"]
