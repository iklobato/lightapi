# LightAPI v2: Annotation-Driven Python REST Framework

[![PyPI version](https://badge.fury.io/py/lightapi.svg)](https://pypi.org/project/lightapi/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**LightAPI** is a Python REST API framework where a single annotated class is simultaneously your ORM model, your Pydantic v2 schema, and your REST endpoint. Declare fields once — LightAPI auto-generates the SQLAlchemy table, validates input, handles CRUD, enforces optimistic locking, filters, paginates, and caches.

---

## Table of Contents

- [Why LightAPI v2?](#why-lightapi-v2)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
  - [RestEndpoint and Field](#restendpoint-and-field)
  - [Auto-injected Columns](#auto-injected-columns)
  - [Optimistic Locking](#optimistic-locking)
  - [HttpMethod Mixins](#httpmethod-mixins)
  - [Serializer](#serializer)
  - [Authentication and Permissions](#authentication-and-permissions)
  - [Filtering, Search, and Ordering](#filtering-search-and-ordering)
  - [Pagination](#pagination)
  - [Custom Queryset](#custom-queryset)
  - [Response Caching](#response-caching)
  - [Middleware](#middleware)
  - [Database Reflection](#database-reflection)
  - [YAML Configuration](#yaml-configuration)
- [Async Support](#async-support)
  - [Enabling Async I/O](#enabling-async-io)
  - [Async Queryset](#async-queryset)
  - [Async Method Overrides](#async-method-overrides)
  - [Background Tasks](#background-tasks)
  - [Async Middleware](#async-middleware)
  - [Sync Endpoints on an Async App](#sync-endpoints-on-an-async-app)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## Why LightAPI v2?

- **One class, three roles**: Your `RestEndpoint` subclass is the SQLAlchemy ORM model, the Pydantic v2 schema, *and* the HTTP handler — no separate files, no boilerplate.
- **Annotation-driven columns**: Write `title: str = Field(min_length=1)` — LightAPI creates the `VARCHAR` column, the Pydantic constraint, and the API validation all at once.
- **Optimistic locking built in**: Every endpoint gets a `version` field. `PUT`/`PATCH` require `version` in the body; mismatches return `409 Conflict`.
- **Opt-in async I/O**: Swap `create_engine` for `create_async_engine` — LightAPI automatically uses `AsyncSession` for every request. Sync and async endpoints coexist on the same app instance.
- **No aiohttp**: Pure Starlette + Uvicorn ASGI stack, no async framework mixing.
- **Pydantic v2**: Full `model_validate`, `model_dump(mode='json')`, `ConfigDict` compatibility.
- **SQLAlchemy 2.0 imperative mapping**: No `DeclarativeBase` inheritance required.

---

## Installation

```bash
# Using uv (recommended)
uv add lightapi

# Or pip
pip install lightapi
```

**Requirements**: Python 3.10+, SQLAlchemy 2.x, Pydantic v2, Starlette, Uvicorn.

**Optional async I/O** (PostgreSQL / SQLite async):

```bash
# asyncpg (PostgreSQL async driver)
uv add "lightapi[async]"
# installs: sqlalchemy[asyncio], asyncpg, aiosqlite, greenlet
```

**Optional Redis caching**: `redis` is included as a core dependency but Redis caching only activates when `Meta.cache = Cache(ttl=N)` is set on an endpoint. A `RuntimeWarning` is emitted at startup if Redis is unreachable.

---

## Quick Start

```python
from sqlalchemy import create_engine
from lightapi import LightApi, RestEndpoint, Field

class BookEndpoint(RestEndpoint):
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)

engine = create_engine("sqlite:///books.db")
app = LightApi(engine=engine)
app.register({"/books": BookEndpoint})

if __name__ == "__main__":
    app.run()
```

That's it. You now have:

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/books` | List all books (`{"results": [...]}`) |
| `POST` | `/books` | Create a book (validates `title` min_length=1) |
| `GET` | `/books/{id}` | Retrieve one book |
| `PUT` | `/books/{id}` | Full update (requires `version`) |
| `PATCH` | `/books/{id}` | Partial update (requires `version`) |
| `DELETE` | `/books/{id}` | Delete (returns 204) |

```bash
# Create
curl -X POST http://localhost:8000/books \
  -H "Content-Type: application/json" \
  -d '{"title": "Clean Code", "author": "Robert Martin"}'
# → 201 {"id": 1, "title": "Clean Code", "author": "Robert Martin", "version": 1, ...}

# Update (must supply version)
curl -X PUT http://localhost:8000/books/1 \
  -H "Content-Type: application/json" \
  -d '{"title": "Clean Code (2nd Ed)", "author": "Robert Martin", "version": 1}'
# → 200 {"id": 1, "version": 2, ...}

# Stale version
curl -X PUT http://localhost:8000/books/1 \
  -H "Content-Type: application/json" \
  -d '{"title": "Clash", "author": "X", "version": 1}'
# → 409 {"detail": "version conflict"}
```

---

## Core Concepts

### RestEndpoint and Field

Declare fields using Python type annotations and `Field()`:

```python
from lightapi import RestEndpoint, Field
from typing import Optional
from decimal import Decimal

class ProductEndpoint(RestEndpoint):
    name: str = Field(min_length=1, max_length=200)
    price: Decimal = Field(ge=0, decimal_places=2)
    category: str = Field(min_length=1)
    description: Optional[str] = None  # nullable column, no constraint
    in_stock: bool = Field(default=True)
```

**Supported types and their SQLAlchemy column mappings:**

| Python annotation | Column type | Nullable |
|---|---|---|
| `str` | `VARCHAR` | No |
| `Optional[str]` | `VARCHAR` | Yes |
| `int` | `INTEGER` | No |
| `Optional[int]` | `INTEGER` | Yes |
| `float` | `FLOAT` | No |
| `bool` | `BOOLEAN` | No |
| `datetime` | `DATETIME` | No |
| `Decimal` | `NUMERIC(scale=N)` | No |
| `UUID` | `UUID` | No |

**LightAPI-specific `Field()` kwargs** (stored in `json_schema_extra`, not passed to Pydantic):

| Kwarg | Effect |
|---|---|
| `foreign_key="table.col"` | Adds `ForeignKey` constraint on the column |
| `unique=True` | Adds `UNIQUE` constraint |
| `index=True` | Adds a database index |
| `exclude=True` | Column is skipped entirely (no DB column, no schema field) |
| `decimal_places=N` | Sets `Numeric(scale=N)` (used with `Decimal` type) |

### Auto-injected Columns

Every `RestEndpoint` subclass automatically gets these columns — you never declare them:

| Column | Type | Default |
|---|---|---|
| `id` | `Integer` PK | autoincrement |
| `created_at` | `DateTime` | `utcnow` on insert |
| `updated_at` | `DateTime` | `utcnow` on insert + update |
| `version` | `Integer` | `1` on insert, incremented on each `PUT`/`PATCH` |

`id`, `created_at`, `updated_at`, and `version` are excluded from the create/update input schema but included in all responses.

### Optimistic Locking

Every `PUT` and `PATCH` request **must** include `version` in the JSON body:

```bash
# First fetch the current version
curl http://localhost:8000/products/42
# → {"id": 42, "name": "Widget", "version": 3, ...}

# Update with correct version
curl -X PATCH http://localhost:8000/products/42 \
  -H "Content-Type: application/json" \
  -d '{"name": "Super Widget", "version": 3}'
# → 200 {"id": 42, "name": "Super Widget", "version": 4, ...}

# Concurrent update with stale version → conflict
curl -X PATCH http://localhost:8000/products/42 \
  -H "Content-Type: application/json" \
  -d '{"name": "Other Widget", "version": 3}'
# → 409 {"detail": "version conflict"}
```

Missing `version` returns `422 Unprocessable Entity`.

### HttpMethod Mixins

Control which HTTP verbs your endpoint exposes by mixing in `HttpMethod.*` classes:

```python
from lightapi import RestEndpoint, HttpMethod, Field

class ReadOnlyEndpoint(RestEndpoint, HttpMethod.GET):
    """Only GET /items and GET /items/{id} are registered."""
    name: str = Field(min_length=1)

class CreateOnlyEndpoint(RestEndpoint, HttpMethod.POST):
    """Only POST /items is registered."""
    name: str = Field(min_length=1)

class StandardEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST,
                        HttpMethod.PUT, HttpMethod.PATCH, HttpMethod.DELETE):
    """Explicit full CRUD — same as the default with no mixins."""
    name: str = Field(min_length=1)
```

Unregistered methods return `405 Method Not Allowed` with an `Allow` header.

### Serializer

Control which fields appear in responses, globally or per-verb:

```python
from lightapi import RestEndpoint, Serializer, Field

# Form 1 — all verbs, all fields (default)
class Ep1(RestEndpoint):
    name: str = Field(min_length=1)

# Form 2 — restrict to a subset for all verbs
class Ep2(RestEndpoint):
    name: str = Field(min_length=1)
    internal_code: str = Field(min_length=1)
    class Meta:
        serializer = Serializer(fields=["id", "name"])

# Form 3 — different fields for reads vs writes
class Ep3(RestEndpoint):
    name: str = Field(min_length=1)
    class Meta:
        serializer = Serializer(
            read=["id", "name", "created_at", "version"],
            write=["id", "name"],
        )

# Form 4 — reusable subclass, shared across endpoints
class PublicSerializer(Serializer):
    read = ["id", "name", "created_at"]
    write = ["id", "name"]

class Ep4(RestEndpoint):
    name: str = Field(min_length=1)
    class Meta:
        serializer = PublicSerializer

class Ep5(RestEndpoint):
    name: str = Field(min_length=1)
    class Meta:
        serializer = PublicSerializer  # reused
```

### Authentication and Permissions

Use `Meta.authentication` with a backend and an optional permission class:

```python
import os
from lightapi import RestEndpoint, Authentication, Field
from lightapi import JWTAuthentication, IsAuthenticated, IsAdminUser

os.environ["LIGHTAPI_JWT_SECRET"] = "your-secret-key"

class ProtectedEndpoint(RestEndpoint):
    secret: str = Field(min_length=1)
    class Meta:
        authentication = Authentication(backend=JWTAuthentication)

class AdminOnlyEndpoint(RestEndpoint):
    data: str = Field(min_length=1)
    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAdminUser,   # requires payload["is_admin"] == True
        )
```

**Request flow:**
1. `JWTAuthentication.authenticate(request)` — extracts and validates `Authorization: Bearer <token>`, stores payload in `request.state.user`
2. Permission class `.has_permission(request)` — checks `request.state.user`
3. Returns `401` if authentication fails, `403` if permission denied

**Login and token endpoints:** When using `JWTAuthentication` or `BasicAuthentication`, pass `login_validator` to obtain automatic `/auth/login` and `/auth/token` endpoints:

```python
def my_validator(username: str, password: str):
    # Return user payload dict or None
    user = db.query(User).filter_by(username=username).first()
    if user and user.check_password(password):
        return {"sub": str(user.id), "is_admin": user.is_admin}
    return None

app = LightApi(engine=engine, login_validator=my_validator)
app.register({"/secrets": ProtectedEndpoint})
# POST /auth/login and POST /auth/token now accept {"username":"...","password":"..."}
# JWT mode: 200 {"token":"...","user":{...}}; Basic-only: 200 {"user":{...}}
```

**Built-in permission classes:**

| Class | Condition |
|---|---|
| `AllowAny` | Always allowed (default) |
| `IsAuthenticated` | `request.state.user` is not None |
| `IsAdminUser` | `request.state.user["is_admin"] == True` |

### Filtering, Search, and Ordering

Declare filter backends and allowed fields in `Meta.filtering`:

```python
from lightapi import RestEndpoint, Filtering, Field
from lightapi.filters import FieldFilter, SearchFilter, OrderingFilter

class ArticleEndpoint(RestEndpoint):
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    author: str = Field(min_length=1)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["category"],           # ?category=news  (exact match)
            search=["title", "author"],    # ?search=python  (case-insensitive LIKE)
            ordering=["title", "author"],  # ?ordering=title or ?ordering=-title
        )
```

**Query parameters:**

```bash
# Exact filter (whitelisted fields only)
GET /articles?category=news

# Full-text search across title and author
GET /articles?search=python

# Ordering (prefix - for descending)
GET /articles?ordering=-title

# Combine all
GET /articles?category=news&search=python&ordering=-title
```

### Pagination

```python
from lightapi import RestEndpoint, Pagination, Field

class PostEndpoint(RestEndpoint):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)

    class Meta:
        pagination = Pagination(style="page_number", page_size=20)
```

**Page-number pagination** (`style="page_number"`):

```bash
GET /posts?page=2
# → {"count": 150, "pages": 8, "next": "...", "previous": "...", "results": [...]}
```

**Cursor pagination** (`style="cursor"`) — keyset-based, O(1) regardless of offset:

```bash
GET /posts
# → {"next": "<base64-cursor>", "previous": null, "results": [...]}

GET /posts?cursor=<base64-cursor>
# → {"next": "<next-cursor>", "previous": null, "results": [...]}
```

### Custom Queryset

Override the base queryset by defining a `queryset` method:

```python
from sqlalchemy import select
from starlette.requests import Request
from lightapi import RestEndpoint, Field

class PublishedArticleEndpoint(RestEndpoint):
    title: str = Field(min_length=1)
    published: bool = Field()

    def queryset(self, request: Request):
        cls = type(self)
        return select(cls._model_class).where(cls._model_class.published == True)
```

`GET /publishedarticles` now returns only published articles, while `GET /publishedarticles/{id}` still retrieves any row by primary key.

### Response Caching

Cache `GET` responses in Redis by setting `Meta.cache`:

```python
from lightapi import RestEndpoint, Cache, Field

class ProductEndpoint(RestEndpoint):
    name: str = Field(min_length=1)
    price: float = Field(ge=0)

    class Meta:
        cache = Cache(ttl=60)   # cache GET responses for 60 seconds
```

- Only `GET` (list and retrieve) responses are cached.
- `POST`, `PUT`, `PATCH`, `DELETE` automatically invalidate the cache for that endpoint's key prefix.
- If Redis is unreachable at `app.run()`, a `RuntimeWarning` is emitted and caching is silently skipped.

Set the Redis URL via environment variable:

```bash
export LIGHTAPI_REDIS_URL="redis://localhost:6379/0"
```

### Middleware

Implement `Middleware.process(request, response)`:

- Called with `response=None` **before** the endpoint — return a `Response` to short-circuit.
- Called with the endpoint's response **after** — modify and return it, or return the response unchanged.

```python
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from lightapi import LightApi, RestEndpoint, Field
from lightapi.core import Middleware

class RateLimitMiddleware(Middleware):
    def process(self, request: Request, response: Response | None) -> Response | None:
        if response is None:  # pre-processing
            if request.headers.get("X-Rate-Limit-Exceeded"):
                return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        return response  # post-processing: passthrough

class MyEndpoint(RestEndpoint):
    name: str = Field(min_length=1)

app = LightApi(engine=engine, middlewares=[RateLimitMiddleware])
app.register({"/items": MyEndpoint})
```

Middlewares are applied in declaration order (pre-phase) and reversed (post-phase).

### Database Reflection

Map an existing database table without declaring columns:

```python
class LegacyUserEndpoint(RestEndpoint):
    class Meta:
        reflect = True
        table = "legacy_users"   # existing table name in the database
```

Extend an existing table with additional columns:

```python
class ExtendedEndpoint(RestEndpoint):
    new_field: str = Field(min_length=1)

    class Meta:
        reflect = "partial"
        table = "existing_table"   # reflect + add new_field column
```

`ConfigurationError` is raised at `app.register()` time if the table does not exist.

### YAML Configuration

Boot `LightApi` from a YAML file using `LightApi.from_config()`. Two formats are
supported — pick whichever fits your project.

#### Declarative format (recommended)

Define endpoints, fields, and all `Meta` options directly in YAML. No Python
`RestEndpoint` classes required.

```yaml
# lightapi.yaml
database:
  url: "${DATABASE_URL}"        # ${VAR} env-var substitution

cors_origins:
  - "https://myapp.com"

# Global defaults applied to every endpoint unless overridden
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
  - route: /products
    fields:
      name:        { type: str, max_length: 200 }
      price:       { type: float }
      in_stock:    { type: bool, default: true }
    meta:
      methods: [GET, POST, PUT, DELETE]
      filtering:
        fields:   [in_stock]
        ordering: [price]

  - route: /orders
    fields:
      reference: { type: str }
      total:     { type: float }
    meta:
      methods: [GET, POST]
      # Override the global default for this endpoint only
      authentication:
        permission: AllowAny
```

```python
from lightapi import LightApi

app = LightApi.from_config("lightapi.yaml")
app.run()
```

#### YAML field reference

| Field | Type | Description |
|-------|------|-------------|
| `database.url` | string | SQLAlchemy URL. Supports `${VAR}` env substitution. |
| `cors_origins` | list | CORS allowed origins. |
| `defaults.authentication` | object | `backend` + `permission` applied to every endpoint. |
| `defaults.pagination` | object | `style` + `page_size` applied to every endpoint. |
| `middleware` | list | Class names or dotted paths resolved at startup. |
| `endpoints[].route` | string | URL prefix. |
| `endpoints[].fields` | object | Inline field definitions — `type`, constraints, `optional`. |
| `endpoints[].meta.methods` | list or dict | HTTP methods to enable; dict form allows per-method auth. |
| `endpoints[].meta.authentication` | object | Overrides `defaults.authentication` for this endpoint. |
| `endpoints[].meta.filtering` | object | `fields`, `search`, `ordering` lists. |
| `endpoints[].meta.pagination` | object | `style` + `page_size` for this endpoint. |
| `endpoints[].reflect` | bool | Reflect an existing table — no fields needed. |

Validation is performed by Pydantic v2 at load time. Any schema error raises a
`ConfigurationError` with a precise message pointing to the offending field.

---

## Async Support

LightAPI's async support is **opt-in** and activated by a single change: passing a `create_async_engine` instead of `create_engine`. Everything else — filtering, pagination, serialization, middleware, caching — continues to work unchanged.

### Enabling Async I/O

```bash
uv add "lightapi[async]"   # adds sqlalchemy[asyncio], asyncpg, aiosqlite, greenlet
```

```python
# sync — existing code, no changes required
from sqlalchemy import create_engine
engine = create_engine("postgresql://user:pass@localhost/db")

# async — one-line swap
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
```

Once an `AsyncEngine` is detected, LightAPI:

- Uses `AsyncSession` for every request
- Awaits `async def queryset`, `async def get/post/put/patch/delete` overrides
- Falls back to sync CRUD for endpoints that still define sync methods
- Runs `metadata.create_all` inside the server's event loop via Starlette `on_startup`
- Validates that the async driver (e.g. `asyncpg`, `aiosqlite`) is installed at startup

### Async Queryset

Define `async def queryset` to scope the base query asynchronously:

```python
from sqlalchemy import select
from starlette.requests import Request
from lightapi import RestEndpoint, Field

class OrderEndpoint(RestEndpoint):
    amount: float = Field(ge=0)
    status: str = Field(default="pending")

    async def queryset(self, request: Request):
        # e.g. scope to authenticated user
        user_id = request.state.user["sub"]
        return (
            select(type(self)._model_class)
            .where(type(self)._model_class.owner_id == user_id)
        )
```

`async def queryset` is automatically detected via `asyncio.iscoroutinefunction` and awaited. A plain `def queryset` continues to work on an async app without any changes.

### Async Method Overrides

Override individual HTTP verbs with `async def`:

```python
class ProductEndpoint(RestEndpoint):
    name: str = Field(min_length=1)
    price: float = Field(ge=0)

    async def post(self, request: Request):
        import json
        data = json.loads(await request.body())
        # custom pre-processing ...
        return await self._create_async(data)

    async def get(self, request: Request):
        # custom query, external call, etc.
        return await self._list_async(request)
```

**Built-in async CRUD helpers** available on every `RestEndpoint`:

| Method | Description |
|---|---|
| `await self._list_async(request)` | Paginated list |
| `await self._retrieve_async(request, pk)` | Single row by PK |
| `await self._create_async(data)` | Insert, flush, refresh |
| `await self._update_async(data, pk, partial=False)` | Optimistic-lock update |
| `await self._destroy_async(request, pk)` | Delete |

### Background Tasks

Call `self.background(fn, *args, **kwargs)` inside any async method override to schedule a fire-and-forget task. The task runs after the HTTP response is sent (Starlette `BackgroundTasks`):

```python
async def notify(order_id: int) -> None:
    # send email, write audit log, push notification …
    ...

class OrderEndpoint(RestEndpoint):
    amount: float = Field(ge=0)

    async def post(self, request: Request):
        import json
        resp = await self._create_async(json.loads(await request.body()))
        if resp.status_code == 201:
            import json as _json
            self.background(notify, _json.loads(resp.body)["id"])
        return resp
```

Both `def` (sync) and `async def` callables are accepted by Starlette's `BackgroundTasks`. Calling `self.background()` outside a request handler raises `RuntimeError`.

### Async Middleware

`Middleware.process` can be a coroutine — LightAPI awaits it automatically. Sync and async middleware coexist in the same list:

```python
from lightapi.core import Middleware
from starlette.requests import Request
from starlette.responses import Response

class AsyncAuditMiddleware(Middleware):
    async def process(self, request: Request, response: Response | None) -> None:
        if response is None:
            await write_audit_log(request)   # async I/O
        return None

class SyncHeaderMiddleware(Middleware):
    def process(self, request: Request, response: Response | None) -> None:
        if response is not None:
            response.headers["X-Served-By"] = "lightapi"
        return None

app = LightApi(engine=engine, middlewares=[AsyncAuditMiddleware, SyncHeaderMiddleware])
```

Pre-processing order: `AsyncAuditMiddleware → SyncHeaderMiddleware`.
Post-processing order (reversed): `SyncHeaderMiddleware → AsyncAuditMiddleware`.

### Sync Endpoints on an Async App

Endpoints that still define sync methods work without modification on an async-engine app:

```python
class TagEndpoint(RestEndpoint):
    label: str = Field(min_length=1)

    def queryset(self, request: Request):          # sync — still works
        return select(type(self)._model_class)
```

LightAPI detects whether `queryset` / the override method is async and dispatches accordingly. No runtime penalty on the sync path.

### Session Helpers

`get_sync_session` and `get_async_session` are exported from `lightapi` for use in custom code:

```python
from lightapi import get_sync_session, get_async_session

# Sync
with get_sync_session(engine) as session:
    rows = session.execute(select(MyModel)).scalars().all()

# Async
async with get_async_session(async_engine) as session:
    rows = (await session.execute(select(MyModel))).scalars().all()
```

Both context managers commit on clean exit and roll back on exception.

### Testing Async Endpoints

Use `pytest-asyncio` and `httpx.AsyncClient` with an in-memory `aiosqlite` engine:

```python
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication
from pydantic import Field

@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    class Widget(RestEndpoint):
        name: str = Field(min_length=1)
        class Meta:
            authentication = Authentication(permission=AllowAny)

    app = LightApi(engine=engine)
    app.register({"/widgets": Widget})
    async with AsyncClient(
        transport=ASGITransport(app=app.build_app()), base_url="http://test"
    ) as c:
        yield c

async def test_create_widget(client):
    r = await client.post("/widgets", json={"name": "bolt"})
    assert r.status_code == 201
    assert r.json()["name"] == "bolt"
```

Add to `pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
```

---

## API Reference

### `LightApi`

```python
LightApi(
    engine=None,           # SQLAlchemy engine (takes priority over database_url)
    database_url=None,     # Fallback: create_engine(database_url)
    cors_origins=None,     # List[str] of allowed CORS origins
    middlewares=None,      # List[type] of Middleware subclasses
)
```

| Method | Description |
|---|---|
| `register(mapping)` | `{"/path": EndpointClass, ...}` — register endpoints and build routes |
| `build_app()` | Create tables and return the Starlette ASGI app (for testing) |
| `run(host, port, debug, reload)` | Create tables, check caches, start uvicorn |
| `LightApi.from_config(path)` | Class method — construct from a YAML file |

### `RestEndpoint`

| Attribute | Type | Description |
|---|---|---|
| `_meta` | `dict` | Parsed Meta configuration |
| `_allowed_methods` | `set[str]` | HTTP verbs this endpoint handles |
| `_model_class` | `type` | SQLAlchemy-mapped class (same as `type(self)`) |
| `__schema_create__` | `ModelMetaclass` | Pydantic model for POST/PUT/PATCH input |
| `__schema_read__` | `ModelMetaclass` | Pydantic model for responses |

Override these methods to customise behaviour. Both `def` (sync) and `async def` (async) variants are detected automatically:

| Method | Signature | Default behaviour |
|---|---|---|
| `list` | `(request)` | `SELECT *` + optional filter/pagination |
| `retrieve` | `(request, pk)` | `SELECT WHERE id=pk` |
| `create` | `(data)` | `INSERT RETURNING` |
| `update` | `(data, pk, partial)` | `UPDATE WHERE id=pk AND version=N RETURNING` |
| `destroy` | `(request, pk)` | `DELETE WHERE id=pk` |
| `queryset` | `(request)` | Returns base `select(cls._model_class)` |
| `get` | `(request)` | Override GET (collection or detail) |
| `post` | `(request)` | Override POST |
| `put` | `(request)` | Override PUT |
| `patch` | `(request)` | Override PATCH |
| `delete` | `(request)` | Override DELETE |

**Async CRUD helpers** (available when using an async engine):

| Helper | Description |
|---|---|
| `_list_async(request)` | Async `SELECT *` with pagination |
| `_retrieve_async(request, pk)` | Async `SELECT WHERE id=pk` |
| `_create_async(data)` | Async `INSERT` with flush/refresh |
| `_update_async(data, pk, partial)` | Async optimistic-lock `UPDATE` |
| `_destroy_async(request, pk)` | Async `DELETE` |
| `background(fn, *args, **kwargs)` | Schedule a post-response background task |

### `Meta` inner class

```python
class MyEndpoint(RestEndpoint):
    class Meta:
        authentication = Authentication(backend=..., permission=...)
        filtering = Filtering(backends=[...], fields=[...], search=[...], ordering=[...])
        pagination = Pagination(style="page_number"|"cursor", page_size=20)
        serializer = Serializer(fields=[...]) | Serializer(read=[...], write=[...])
        cache = Cache(ttl=60)
        reflect = False | True | "partial"
        table = "custom_table_name"     # overrides derived name
```

### Error responses

| Scenario | Status code | Body |
|---|---|---|
| Validation failure | `422` | `{"detail": [...pydantic errors...]}` |
| Not found | `404` | `{"detail": "not found"}` |
| Optimistic lock conflict | `409` | `{"detail": "version conflict"}` |
| Auth failure | `401` | `{"detail": "Authentication credentials invalid."}` |
| Permission denied | `403` | `{"detail": "You do not have permission to perform this action."}` |
| Method not registered | `405` | `{"detail": "Method Not Allowed. Allowed: GET, POST"}` |

---

## Testing

```bash
# Install with dev extras
uv add -e ".[dev]"

# Run all tests (sync + async)
pytest tests/

# Run only async-related tests
pytest tests/test_async_crud.py tests/test_async_session.py \
       tests/test_async_queryset.py tests/test_async_middleware.py \
       tests/test_background_tasks.py tests/test_mixed_sync_async.py \
       tests/test_async_reflection.py

# Run with coverage
pytest tests/ --cov=lightapi --cov-report=term-missing
```

**Async test setup** — add to `pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
```

For sync SQLite in-memory databases in tests, use `StaticPool` to share a single connection:

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient
from lightapi import LightApi, RestEndpoint, Field

class ItemEndpoint(RestEndpoint):
    name: str = Field(min_length=1)

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
app_instance = LightApi(engine=engine)
app_instance.register({"/items": ItemEndpoint})
client = TestClient(app_instance.build_app())
```

---

## Configuration

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `LIGHTAPI_DATABASE_URL` | — | Database connection URL when no `engine` or `database_url` is passed. One of `engine`, `database_url`, or `LIGHTAPI_DATABASE_URL` is required. |
| `LIGHTAPI_JWT_SECRET` | — | Required for `JWTAuthentication` |
| `LIGHTAPI_REDIS_URL` | `redis://localhost:6379/0` | Redis URL for response caching |

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install uv && uv pip install --system -e .
COPY . .
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      LIGHTAPI_DATABASE_URL: postgresql://postgres:pass@db:5432/mydb
      LIGHTAPI_JWT_SECRET: change-me-in-production
      LIGHTAPI_REDIS_URL: redis://redis:6379/0
    depends_on: [db, redis]
  db:
    image: postgres:16-alpine
    environment: {POSTGRES_DB: mydb, POSTGRES_USER: postgres, POSTGRES_PASSWORD: pass}
  redis:
    image: redis:7-alpine
```

---

## Contributing

```bash
git clone https://github.com/iklobato/lightapi.git
cd lightapi
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest tests/

# Lint and format
ruff check lightapi/
ruff format lightapi/

# Type check
mypy lightapi/
```

Guidelines:
1. Fork the repository and create a feature branch
2. Write tests for new features — all existing tests must remain green
3. Follow the existing code style (PEP 8, type hints everywhere)
4. Submit a pull request with a clear description of the change

Bug reports: Please open a GitHub issue with Python version, LightAPI version, a minimal reproduction, and the full traceback.

---

## License

LightAPI is released under the MIT License. See [LICENSE](LICENSE) for details.

---

## Acknowledgments

- **Starlette** — ASGI framework and routing
- **SQLAlchemy 2.0** — ORM and imperative mapping
- **Pydantic v2** — Data validation and schema generation
- **Uvicorn** — ASGI server
- **PyJWT** — JWT token handling

---

**Get started:**

```bash
uv pip install lightapi
```
