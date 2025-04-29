---
title: Configuration
---

LightAPI provides several configuration options to customize your application's behavior. You can pass these as keyword arguments to the `LightApi` constructor, or set environment variables for a production deployment.

## Constructor Parameters

- `host` (str, default `'127.0.0.1'`): Host address for the server to bind.
- `port` (int, default `8000`): Port number for incoming HTTP requests.
- `debug` (bool, default `False`): Enable debug mode with auto-reload and detailed error responses.
- `reload` (bool, default `False`): Enable automatic server restart on code changes (uses Uvicorn's reload).
- `database_url` (str): Connection URL for your database (e.g., `sqlite+aiosqlite:///./app.db`, `postgresql+asyncpg://user:pass@host/dbname`).
- `cors_origins` (List[str], default empty): List of origins allowed for CORS. Use `['*']` for all.
- `jwt_secret` (str, required for JWT auth): Secret key for encoding and decoding JWT tokens.

## Environment Variables

You can also configure your app using environment variables. LightAPI will read these at startup:

- `LIGHTAPI_HOST`
- `LIGHTAPI_PORT`
- `LIGHTAPI_DEBUG`
- `LIGHTAPI_RELOAD`
- `LIGHTAPI_DATABASE_URL`
- `LIGHTAPI_CORS_ORIGINS`
- `LIGHTAPI_JWT_SECRET`

Environment variables take precedence over constructor parameters if both are provided.

## Example Configuration File

```ini
# .env
LIGHTAPI_HOST=0.0.0.0
LIGHTAPI_PORT=8080
LIGHTAPI_DEBUG=True
LIGHTAPI_DATABASE_URL=sqlite+aiosqlite:///./app.db
LIGHTAPI_CORS_ORIGINS=["https://example.com"]
LIGHTAPI_JWT_SECRET=supersecretkey
```

Use `python-dotenv` or your own environment loader to populate these variables before starting your app.
