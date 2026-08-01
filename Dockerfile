# syntax=docker/dockerfile:1.7

# Ready-to-run LightAPI image.
# Users mount their config at /app/lightapi.yaml and run the container —
# no Python code or build step required on their side.
#
# Build:    docker build -t lightapi:local .
# Run:      docker run --rm -p 8000:8000 \
#               -v "$(pwd)/lightapi.yaml:/app/lightapi.yaml:ro" \
#               -e DATABASE_URL=sqlite:////app/data.db \
#               lightapi:local

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

# Build dependencies for psycopg2 / asyncpg native code. Keep build-essential
# in the layer so we can compile, then remove it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Install LightAPI + async + PostgreSQL drivers. We use the published wheel
# rather than copying the source so the image stays useful even when this
# Dockerfile is built outside the repo.
ARG LIGHTAPI_VERSION
RUN if [ -n "$LIGHTAPI_VERSION" ]; then \
        pip install "lightapi[async]==$LIGHTAPI_VERSION" psycopg2-binary ; \
    else \
        pip install "lightapi[async]" psycopg2-binary ; \
    fi \
 && apt-get purge -y --auto-remove build-essential \
 && rm -rf /root/.cache

# Copy the launcher. Everything user-supplied lives outside /app/entrypoint.py.
COPY docker/entrypoint.py /app/entrypoint.py

# Non-root runtime user
RUN groupadd --system --gid 1001 lightapi \
 && useradd  --system --uid 1001 --gid lightapi --home-dir /app --no-create-home lightapi \
 && chown -R lightapi:lightapi /app
USER lightapi

EXPOSE 8000

# Lightweight health check — touches the root path expecting any HTTP response.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
import os; \
url='http://127.0.0.1:'+os.environ.get('LIGHTAPI_PORT','8000')+'/'; \
sys.exit(0 if urllib.request.urlopen(url, timeout=2).status else 1)" \
    || exit 1

ENTRYPOINT ["python", "/app/entrypoint.py"]
