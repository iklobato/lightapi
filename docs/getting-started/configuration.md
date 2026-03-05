---
title: Configuration Guide
description: Complete guide to configuring LightAPI v2 applications
---

# Configuration Guide

LightAPI v2 is configured through Python code or a `lightapi.yaml` file. There are no magic environment-variable-only globals — every option is explicit.

## Python Configuration

### `LightApi(...)` constructor

```python
from sqlalchemy import create_engine
from lightapi import LightApi, Middleware

engine = create_engine("sqlite:///app.db")

app = LightApi(
    engine=engine,                        # SQLAlchemy Engine (sync or async)
    cors_origins=["https://myapp.com"],   # CORS allowed origins
    middlewares=[MyMiddleware],            # List of Middleware subclasses
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `engine` | `Engine \| AsyncEngine` | auto | SQLAlchemy engine. If omitted, falls back to `database_url`. |
| `database_url` | `str` | `config.database_url` | Creates a sync engine from this URL if `engine` is not given. |
| `cors_origins` | `list[str]` | `[]` | Domains allowed for cross-origin requests. |
| `middlewares` | `list[type]` | `[]` | `Middleware` subclasses applied to every request. |

### Registering endpoints

```python
from lightapi import LightApi, RestEndpoint, Field

class UserEndpoint(RestEndpoint):
    username: str = Field(min_length=3)
    email: str

app = LightApi(engine=engine)
app.register({
    "/users": UserEndpoint,
    "/posts": PostEndpoint,
})
```

`register()` accepts a `dict[str, type]` mapping URL prefixes to `RestEndpoint` subclasses. It creates the database tables and registers both collection (`/users`) and detail (`/users/{id}`) routes automatically.

### Running the server

```python
app.run(host="0.0.0.0", port=8000, debug=False, reload=False)
```

Or as an ASGI app (e.g. with Gunicorn + Uvicorn workers):

```python
asgi_app = app.build_app()
```

## YAML Configuration

Use `LightApi.from_config()` to bootstrap from a YAML file:

```yaml
# lightapi.yaml
database_url: "${DATABASE_URL}"   # supports ${ENV_VAR} substitution
cors_origins:
  - "https://myapp.com"

endpoints:
  - path: /users
    class: myapp.endpoints.UserEndpoint
  - path: /posts
    class: myapp.endpoints.PostEndpoint
```

```python
from lightapi import LightApi

app = LightApi.from_config("lightapi.yaml")
app.run()
```

### YAML fields

| Field | Type | Description |
|-------|------|-------------|
| `database_url` | string | SQLAlchemy database URL. Supports `${VAR}` env substitution. |
| `cors_origins` | list | CORS allowed origins. |
| `endpoints` | list | Each entry has `path` (URL prefix) and `class` (dotted import path). |

### Environment variable substitution

```yaml
database_url: "${DATABASE_URL}"
```

If `DATABASE_URL` is not set at runtime, LightAPI raises a `ConfigurationError` with a clear message.

## Async engine

Switching to async I/O requires only changing the engine:

```python
from sqlalchemy.ext.asyncio import create_async_engine
from lightapi import LightApi

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/mydb")
app = LightApi(engine=engine)
```

Install the async extras first:

```bash
uv add "lightapi[async]"
```

See [Async Support](../advanced/async.md) for the full guide.

## CORS

Pass a list of allowed origins to enable CORS headers on every response:

```python
app = LightApi(
    engine=engine,
    cors_origins=["https://myapp.com", "https://admin.myapp.com"],
)
```

Use `["*"]` to allow all origins (not recommended for production).

## Middleware

Register middleware globally at startup:

```python
from lightapi import LightApi, Middleware
from starlette.requests import Request

class RequestLogMiddleware(Middleware):
    def process(self, request: Request) -> None:
        print(f"{request.method} {request.url.path}")

app = LightApi(engine=engine, middlewares=[RequestLogMiddleware])
```

See [Middleware](../advanced/middleware.md) for detailed documentation.

## Environment variables

LightAPI reads the following environment variables:

| Variable | Description |
|----------|-------------|
| `LIGHTAPI_DATABASE_URL` | Default database URL when no `engine` or `database_url` is passed. |
| `LIGHTAPI_JWT_SECRET` | Secret key used by `JWTAuthentication`. Required when JWT auth is used. |

## Per-endpoint configuration (`Meta`)

Each `RestEndpoint` subclass can have an inner `Meta` class that controls its behaviour:

```python
from lightapi import (
    RestEndpoint, Field,
    Authentication, Filtering, Pagination, Serializer, Cache,
    JWTAuthentication, IsAuthenticated,
    FieldFilter, SearchFilter, OrderingFilter,
    RedisCache,
)

class ArticleEndpoint(RestEndpoint):
    title: str
    body: str
    published: bool = Field(default=False)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
        )
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["published"],
            search=["title", "body"],
            ordering=["title", "created_at"],
        )
        pagination = Pagination(style="page_number", page_size=20)
        serializer = Serializer(read=["id", "title", "published", "created_at"])
        cache = Cache(ttl=300)
```

| `Meta` attribute | Type | Description |
|-----------------|------|-------------|
| `authentication` | `Authentication` | Auth backend + permission class |
| `filtering` | `Filtering` | Filter backends, allowed fields, search fields, ordering fields |
| `pagination` | `Pagination` | Pagination style (`page_number` or `cursor`) and page size |
| `serializer` | `Serializer` | Field visibility for read/write |
| `cache` | `Cache` | Response caching TTL and vary-on keys |
| `reflect` | `bool` | Set `True` to reflect an existing table instead of creating one |
| `table` | `str` | Override the inferred table name |

See the individual sections in [Advanced Topics](../advanced/) for full details on each option.
