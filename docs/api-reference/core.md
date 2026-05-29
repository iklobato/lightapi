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
    mode: str | None = None,
    cors_origins: list[str] | None = None,
    middlewares: list[type] | None = None,
    auth_path: str = "/auth",
    session_manager: SessionManager | None = None,
    rate_limiter: "RateLimiter | dict[str, int] | None" = None,
    login_validator: Callable[[str, str], dict[str, Any] | None] | None = None,
    use_test_isolation: bool = False,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `engine` | `Engine \| AsyncEngine` | SQLAlchemy engine. If omitted, `database_url` or env vars are used. |
| `database_url` | `str \| None` | Creates a sync engine when no `engine` is provided. Falls back to `LIGHTAPI_DATABASE_URL` env var. Raises `ConfigurationError` if none are provided. |
| `mode` | `str \| None` | `"sync"` or `"async"`. Auto-detected from the engine type and from `async def` overrides if omitted. |
| `cors_origins` | `list[str] \| None` | CORS allowed origins. |
| `middlewares` | `list[type] \| None` | `Middleware` subclasses applied globally to all requests. |
| `auth_path` | `str` | Base path for the auto-registered login route. Defaults to `/auth` → `/auth/login` and `/auth/token`. |
| `session_manager` | `SessionManager \| None` | Override the default session manager (advanced; mostly used for test isolation). |
| `rate_limiter` | `RateLimiter \| dict \| None` | Rate-limit config applied to `/auth/login`. Pass a `RateLimiter` instance or a `{"requests_per_minute": N, ...}` dict. |
| `login_validator` | `Callable[[str, str], dict \| None]` | Callable `(username, password) → dict \| None`. Returns a payload dict on success, or `None` to reject. Raising an exception is treated the same as returning `None` — the client receives 401 and the exception is logged at WARNING level. |
| `use_test_isolation` | `bool` | When `True`, mounts each registered endpoint onto a unique table name and a per-thread metadata/registry — used by the test suite. |

### `register(mapping)`

```python
app.register({
    "/users": UserEndpoint,
    "/posts": PostEndpoint,
})
```

Accepts a `dict[str, type]` mapping URL prefixes to `RestEndpoint` subclasses.

- Registers collection (`/users`) and detail (`/users/{id}`) Starlette routes.
- Maps each `RestEndpoint` class onto a SQLAlchemy table (table created later by `build_app()` / `run()`).
- Auto-registers `/auth/login` and `/auth/token` if any endpoint declares `Authentication(backend=JWTAuthentication)` or `Authentication(backend=BasicAuthentication)`.

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

### `from_dict(config: dict) → LightApi`

```python
app = LightApi.from_dict({
    "database_url": "sqlite:///db.sqlite3",
    "endpoints": {
        "/books": {
            "fields": {"title": str, "author": str},
            "auth": "jwt",
        },
        "/authors": {"fields": {"name": str}},
    },
    "cors": ["https://myapp.com"],
})
```

The `methods` key in each endpoint config accepts a list of HTTP verbs (`["GET", "POST"]`, etc.) and is enforced — unlisted methods return `405 Method Not Allowed`.

Programmatic alternative to YAML for simple configurations.

```yaml
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
