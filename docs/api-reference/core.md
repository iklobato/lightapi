---
title: Core API Reference
description: LightApi class, Middleware, and CORS in LightAPI v2
---

# Core API Reference

## `LightApi`

```python
from lightapi import LightApi
```

The main application class.

### Constructor

```python
LightApi(
    engine=None,
    database_url: str | None = None,
    cors_origins: list[str] | None = None,
    middlewares: list[type] | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `engine` | `Engine \| AsyncEngine` | SQLAlchemy engine. If omitted, `database_url` is used. |
| `database_url` | `str \| None` | Creates a sync engine when no `engine` is provided. Falls back to `LIGHTAPI_DATABASE_URL` env var. |
| `cors_origins` | `list[str] \| None` | CORS allowed origins. |
| `middlewares` | `list[type] \| None` | `Middleware` subclasses applied globally to all requests. |

### `register(mapping)`

```python
app.register({
    "/users": UserEndpoint,
    "/posts": PostEndpoint,
})
```

Accepts a `dict[str, type]` mapping URL prefixes to `RestEndpoint` subclasses.

- Creates missing database tables.
- Registers collection (`/users`) and detail (`/users/{id}`) Starlette routes.

### `build_app() → Starlette`

Returns the Starlette ASGI application without starting the server. Use for testing or embedding in other ASGI apps:

```python
starlette_app = app.build_app()
```

### `run(host, port, debug, reload)`

```python
app.run(host="0.0.0.0", port=8000, debug=False, reload=False)
```

Starts the Uvicorn server.

### `from_config(config_path) → LightApi`

```python
app = LightApi.from_config("lightapi.yaml")
```

Bootstraps a `LightApi` instance from a YAML file. The YAML document is parsed
and validated by Pydantic v2 — any schema error raises `ConfigurationError` with
a precise message before the server starts.

Two formats are accepted:

- **Declarative** (`database.url` + `endpoints[].route` + `endpoints[].fields`):
  endpoints are generated dynamically; no `RestEndpoint` subclasses needed.
- **Legacy** (`database_url` + `endpoints[].path` + `endpoints[].class`):
  loads existing `RestEndpoint` subclasses by dotted import path.

```yaml
# declarative
database:
  url: "${DATABASE_URL}"
defaults:
  authentication: { backend: JWTAuthentication, permission: IsAuthenticated }
endpoints:
  - route: /items
    fields:
      name:  { type: str }
      price: { type: float }
    meta:
      methods: [GET, POST, PUT, DELETE]
```

```yaml
# legacy
database_url: "${DATABASE_URL}"
endpoints:
  - path: /items
    class: myapp.endpoints.ItemEndpoint
```

See [Configuration Guide](../getting-started/configuration.md) for the complete schema reference including all `defaults`, `meta`, `filtering`, `pagination`, and per-method auth options.

## `Middleware`

```python
from lightapi import Middleware
# or: from lightapi.core import Middleware
```

Base class for request/response middleware.

```python
from starlette.requests import Request
from starlette.responses import Response
from lightapi import Middleware

class TimingMiddleware(Middleware):
    def process(self, request: Request, response: Response | None = None) -> None:
        if response is None:
            # pre-request
            request.state.start = time.time()
        else:
            # post-response
            elapsed = time.time() - request.state.start
            print(f"{request.url.path} took {elapsed:.3f}s")
```

For async middleware, define `async def process`:

```python
class AsyncAuditMiddleware(Middleware):
    async def process(self, request: Request, response: Response | None = None) -> None:
        if response is not None:
            await save_audit_log(request, response)
```

See [Middleware](../advanced/middleware.md) for details.

## `CORSMiddleware`

```python
from lightapi import CORSMiddleware
# or: from lightapi.core import CORSMiddleware
```

CORS middleware. LightAPI applies it automatically when `cors_origins` is set. You can also register it explicitly:

```python
app = LightApi(engine=engine, middlewares=[CORSMiddleware])
```

## `AuthenticationMiddleware`

```python
from lightapi import AuthenticationMiddleware
# or: from lightapi.core import AuthenticationMiddleware
```

Global authentication middleware. Prefer per-endpoint `Meta.authentication` instead — this class is available for backward compatibility.

## `Response`

```python
from lightapi import Response
# or: from lightapi.core import Response
```

A thin wrapper around Starlette's response. Used by the built-in CRUD methods. For new code, prefer `starlette.responses.JSONResponse` directly.
