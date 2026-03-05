---
title: LightAPI v2 Documentation
description: Annotation-driven Python REST framework — one class, three roles
---

# LightAPI v2 Documentation

**LightAPI v2** is a Python REST API framework where a single annotated class simultaneously acts as your SQLAlchemy ORM model, your Pydantic v2 validation schema, and your HTTP endpoint. No more keeping three files in sync — declare once, get everything.

Built on **Starlette + Uvicorn**, validated by **Pydantic v2**, persisted via **SQLAlchemy 2.0 imperative mapping**.

---

## Key Features

### One Class, Three Roles
- **Annotation-driven columns** — `title: str = Field(min_length=1)` creates a `VARCHAR NOT NULL` column, a Pydantic constraint, and an API validation rule simultaneously
- **Auto-injected audit columns** — every endpoint gets `id`, `created_at`, `updated_at`, `version` automatically
- **Full CRUD** — `GET`, `POST`, `PUT`, `PATCH`, `DELETE` generated from a single class definition

### Data Integrity
- **Optimistic locking** — every `PUT`/`PATCH` requires `version` in the body; stale writes return `409 Conflict`
- **Pydantic v2 validation** — `422 Unprocessable Entity` with structured error details on bad input
- **Consistent error format** — `{"detail": "..."}` or `{"detail": [...pydantic errors...]}` across all errors

### Security
- **JWT Authentication** — `Meta.authentication = Authentication(backend=JWTAuthentication)`
- **Permission classes** — `AllowAny`, `IsAuthenticated`, `IsAdminUser` (checks `is_admin` JWT claim)
- **CORS** — `LightApi(cors_origins=[...])`

### Querying
- **Filter backends** — `FieldFilter` (exact match with type coercion), `SearchFilter` (LIKE), `OrderingFilter`
- **Pagination** — page-number or cursor (keyset) styles via `Meta.pagination`
- **Custom queryset** — override `queryset(self, request)` to scope the base query

### Async I/O (opt-in)
- **Single engine swap** — pass `create_async_engine(...)` instead of `create_engine(...)` to activate full async I/O
- **Async queryset** — `async def queryset` is detected and awaited automatically
- **Async method overrides** — `async def post/get/put/patch/delete` coexist with sync overrides on the same app
- **Background tasks** — `self.background(fn, *args)` schedules post-response fire-and-forget tasks
- **Mixed middleware** — `async def process` and `def process` middleware coexist in the same stack
- **Async reflection** — `Meta.reflect = True` works with `AsyncEngine` via `conn.run_sync`

### Developer Experience
- **Redis caching** — `Meta.cache = Cache(ttl=60)` caches `GET` responses; writes auto-invalidate
- **HttpMethod mixins** — `class MyEp(RestEndpoint, HttpMethod.GET, HttpMethod.POST)` for explicit verb control
- **Serializer** — `Meta.serializer = Serializer(read=[...], write=[...])` for per-verb field projection
- **Middleware** — `Middleware.process(request, response)` — sync or async — with short-circuit support
- **Database reflection** — map existing tables with `Meta.reflect = True | "partial"`
- **YAML config** — `LightApi.from_config("lightapi.yaml")`

---

## Quick Start

=== "Sync (SQLite)"

    ```bash
    uv add lightapi
    ```

    ```python
    from sqlalchemy import create_engine
    from lightapi import LightApi, RestEndpoint, Field
    from typing import Optional

    class BookEndpoint(RestEndpoint):
        title: str = Field(min_length=1)
        author: str = Field(min_length=1)
        year: Optional[int] = None

    engine = create_engine("sqlite:///books.db")
    app = LightApi(engine=engine)
    app.register({"/books": BookEndpoint})
    app.run()
    ```

=== "Async (PostgreSQL)"

    ```bash
    uv add "lightapi[async]"
    ```

    ```python
    from sqlalchemy.ext.asyncio import create_async_engine
    from lightapi import LightApi, RestEndpoint, Field
    from typing import Optional

    class BookEndpoint(RestEndpoint):
        title: str = Field(min_length=1)
        author: str = Field(min_length=1)
        year: Optional[int] = None

    engine = create_async_engine(
        "postgresql+asyncpg://user:pass@localhost/mydb"
    )
    app = LightApi(engine=engine)
    app.register({"/books": BookEndpoint})
    app.run()
    ```

See the [Quickstart Guide](getting-started/quickstart.md) for full `curl` examples.

---

## Documentation

### Getting Started
- [Installation](getting-started/installation.md)
- [Quickstart](getting-started/quickstart.md)
- [First Steps](getting-started/first-steps.md)

### Core Concepts
- [RestEndpoint & Field](api-reference/rest.md)
- [Authentication & Permissions](advanced/authentication.md)
- [Filtering & Ordering](advanced/filtering.md)
- [Pagination](advanced/pagination.md)
- [Middleware](advanced/middleware.md)
- [Caching](advanced/caching.md)
- [Database Reflection](api-reference/database.md)
- [YAML Configuration](getting-started/configuration.md)

### Async Support
- [Async Overview](advanced/async.md)

### Reference
- [API Reference](api-reference/rest.md)
- [Error Codes](api-reference/exceptions.md)
- [Configuration](getting-started/configuration.md)

---

## Requirements

- Python **3.10+**
- SQLAlchemy **2.x**
- Pydantic **v2**
- Starlette + Uvicorn

**Async extras** (`lightapi[async]`):

- `sqlalchemy[asyncio]`
- `asyncpg` (PostgreSQL) or `aiosqlite` (SQLite)
- `greenlet`
