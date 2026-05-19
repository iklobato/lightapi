"""Container entrypoint: load lightapi.yaml and start uvicorn.

Resolved configuration values, in order of precedence:

1. Environment variables:
   - LIGHTAPI_CONFIG    Path to the YAML config (default /app/lightapi.yaml).
   - LIGHTAPI_HOST      Host for uvicorn to bind (default 0.0.0.0).
   - LIGHTAPI_PORT      Port for uvicorn (default 8000).
   - LIGHTAPI_LOG_LEVEL Uvicorn log level (default info).
   - DATABASE_URL       Substituted into ${DATABASE_URL} placeholders in the YAML.
   - LIGHTAPI_JWT_SECRET Required when the config uses JWT authentication.
2. Defaults baked into this script.

The YAML schema is documented at
https://iklobato.github.io/lightapi/getting-started/configuration/
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import uvicorn

from lightapi import LightApi

logger = logging.getLogger("lightapi.entrypoint")


def _resolve_config_path() -> Path:
    path = Path(os.environ.get("LIGHTAPI_CONFIG", "/app/lightapi.yaml"))
    if path.exists():
        return path

    sys.stderr.write(
        f"LightAPI config file not found at {path}.\n"
        "Mount your config into the container, for example:\n"
        "    docker run -v ./lightapi.yaml:/app/lightapi.yaml lightapi\n"
        "Or set LIGHTAPI_CONFIG to a different path.\n"
    )
    sys.exit(2)


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LIGHTAPI_LOG_LEVEL", "info").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config_path = _resolve_config_path()
    logger.info("Loading LightAPI config from %s", config_path)

    try:
        app = LightApi.from_config(str(config_path))
    except Exception:
        logger.exception("Failed to load LightAPI config")
        sys.exit(3)

    starlette_app = app.build_app()

    host = os.environ.get("LIGHTAPI_HOST", "0.0.0.0")
    port = int(os.environ.get("LIGHTAPI_PORT", "8000"))
    log_level = os.environ.get("LIGHTAPI_LOG_LEVEL", "info").lower()

    logger.info("Starting uvicorn on %s:%s", host, port)
    uvicorn.run(
        starlette_app,
        host=host,
        port=port,
        log_level=log_level,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
