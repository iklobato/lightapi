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
| `engine` | `Engine \| AsyncEngine` | — | SQLAlchemy engine. If omitted, uses `database_url` or env vars. |
| `database_url` | `str \| None` | — | Creates a sync engine from this URL if `engine` is not given. Falls back to `LIGHTAPI_DATABASE_URL` env var. Raises `ConfigurationError` if none are provided. |
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

Use `LightApi.from_config()` to bootstrap from a YAML file. The YAML schema is
validated by Pydantic v2 at load time, so any typo or missing field produces a
clear `ConfigurationError` message rather than a cryptic runtime crash.

Two formats are supported:

### Declarative format (recommended)

Define every endpoint — fields, HTTP methods, auth, filtering, pagination — entirely
in YAML. No `RestEndpoint` subclasses required.

```yaml
# lightapi.yaml
database:
  url: "${DATABASE_URL}"           # ${VAR} env-var substitution

cors_origins:
  - "https://myapp.com"

# Defaults applied to every endpoint unless overridden
defaults:
  authentication:
    backend: JWTAuthentication
    permission: IsAuthenticated
  pagination:
    style: page_number
    page_size: 20

middleware:
  - CORSMiddleware

endpoints:
  - route: /users
    fields:
      username: { type: str, min_length: 3, max_length: 150 }
      email:    { type: str }
      is_admin: { type: bool, default: false, optional: true }
    meta:
      methods: [GET, POST, PUT, DELETE]
      filtering:
        fields:   [is_admin]
        search:   [username, email]
        ordering: [username]

  - route: /posts
    fields:
      title:     { type: str, max_length: 255 }
      published: { type: bool, default: false }
    meta:
      methods: [GET, POST]
      authentication:
        permission: AllowAny    # override the global default for this endpoint
      pagination:
        page_size: 10
```

```python
from lightapi import LightApi

app = LightApi.from_config("lightapi.yaml")
app.run()
```

### YAML schema reference

| Field | Type | Description |
|-------|------|-------------|
| `database.url` | string | SQLAlchemy URL. Supports `${VAR}` substitution. |
| `cors_origins` | list | CORS allowed origins. |
| `defaults.authentication.backend` | string | Auth backend class name (e.g. `JWTAuthentication`). |
| `defaults.authentication.permission` | string | Permission class name (e.g. `IsAuthenticated`). |
| `defaults.pagination.style` | string | `page_number` or `cursor`. |
| `defaults.pagination.page_size` | int | Rows per page. |
| `middleware` | list | Class names or dotted import paths resolved at startup. |
| `endpoints[].route` | string | URL prefix. |
| `endpoints[].fields` | object | Inline field definitions (see below). |
| `endpoints[].meta.methods` | list or dict | HTTP verbs to enable. Dict form allows per-method auth. |
| `endpoints[].meta.authentication` | object | Overrides `defaults.authentication` for this endpoint. |
| `endpoints[].meta.filtering` | object | `fields`, `search`, `ordering` lists. Backends are auto-selected. |
| `endpoints[].meta.pagination` | object | `style` + `page_size` for this endpoint. |
| `endpoints[].reflect` | bool | Reflect an existing table instead of creating one. |

#### Field definition keys

Each key under `endpoints[].fields` maps a column name to:

| Key | Type | Description |
|-----|------|-------------|
| `type` | string | `str`, `int`, `float`, `bool`, `datetime`, `Decimal` |
| `optional` | bool | Whether the field is `Optional` (default `false`). |
| `default` | any | Default value passed to `Field()`. |
| `min_length` / `max_length` | int | String length constraints. |
| `gt` / `ge` / `lt` / `le` | number | Numeric comparison constraints. |
| `pattern` | string | Regex pattern for strings. |
| `index` | bool | Create a database index. |
| `unique` | bool | Add a UNIQUE constraint. |

### Environment variable substitution

Any `${VAR}` placeholder in a URL field is replaced with the matching environment
variable at load time. A missing variable raises `ConfigurationError` immediately:

```yaml
database:
  url: "${DATABASE_URL}"
```

### Per-method authentication

Use the dict form of `methods` to set different permission classes per HTTP verb:

```yaml
endpoints:
  - route: /articles
    fields:
      title:   { type: str }
      content: { type: str }
    meta:
      methods:
        GET:
          authentication: { permission: AllowAny }
        POST:
          authentication: { permission: IsAuthenticated }
        DELETE:
          authentication: { permission: IsAdminUser }
      authentication:
        backend: JWTAuthentication   # shared backend for all methods
```

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
| `LIGHTAPI_DATABASE_URL` | Database URL when no `engine` or `database_url` is passed. Required when neither is provided. |
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

See the individual sections in [Advanced Topics](../advanced/authentication.md) for full details on each option.
