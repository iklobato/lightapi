---
title: Introduction to LightAPI
description: Learn about LightAPI v2's core concepts and architecture
---

# Introduction to LightAPI

**LightAPI** is a lightweight Python framework for building REST APIs with minimal code. Built on **Starlette + Uvicorn** and **SQLAlchemy**, it lets you define a single class that simultaneously acts as the ORM model, the Pydantic v2 schema, and the HTTP request handler — no separate files, no boilerplate.

## What Makes LightAPI Special?

### One Class, Three Roles

```python
from typing import Optional
from lightapi import LightApi, RestEndpoint, Field
from sqlalchemy import create_engine

class Article(RestEndpoint):
    title: str = Field(min_length=1, max_length=200)
    body: str
    published: Optional[bool] = None

engine = create_engine("sqlite:///blog.db")
app = LightApi(engine=engine)
app.register({"/articles": Article})
```

That single `Article` class:

- Creates an `articles` table with `id`, `title`, `body`, `published`, `created_at`, `updated_at`, `version` columns
- Generates Pydantic v2 schemas for create (write) and read operations
- Exposes `GET /articles`, `POST /articles`, `GET /articles/{id}`, `PUT /articles/{id}`, `PATCH /articles/{id}`, `DELETE /articles/{id}`

### Key Features

| Feature | Description |
|---------|-------------|
| **Auto CRUD** | Full REST endpoints generated from annotated fields |
| **Optimistic locking** | Built-in `version` column prevents lost updates |
| **Pydantic v2 validation** | Request bodies validated automatically with detailed error messages |
| **JWT Authentication** | Protect endpoints with `JWTAuthentication` + permission classes |
| **Filtering** | `FieldFilter`, `SearchFilter`, `OrderingFilter` via query params |
| **Pagination** | `page_number` and `cursor` styles via `Meta.pagination` |
| **Serializer** | Control which fields appear in read vs. write operations |
| **Caching** | Redis-backed response caching via `Meta.cache` |
| **Middleware** | Sync and async `process()` middleware with pre/post hooks |
| **Async I/O** | Swap `create_engine` for `create_async_engine` to enable async |
| **Background tasks** | Fire-and-forget via `self.background(fn, *args)` |
| **Reflection** | Point at an existing database with `Meta.reflect = True` |
| **YAML config** | Bootstrap from a `lightapi.yaml` file via `LightApi.from_config()` |
| **ASGI** | Pure Starlette ASGI app — deploy behind any ASGI server |

## Architecture Overview

```
Request
  │
  ▼
Starlette Router
  │
  ├── Pre-middlewares  (sync or async process())
  │
  ├── RestEndpoint handler
  │     ├── Authentication check
  │     ├── queryset() / async queryset()   ← scope the query
  │     ├── Filtering backends
  │     ├── Pagination
  │     ├── Serializer
  │     └── Cache lookup / store
  │
  ├── Post-middlewares
  │
  └── BackgroundTasks (fire-and-forget after response)
```

## Sync vs. Async

LightAPI supports both sync and async I/O on the same application instance. Async I/O is opt-in — swap `create_engine` for `create_async_engine`:

=== "Sync (SQLite / PostgreSQL)"

    ```python
    from sqlalchemy import create_engine
    from lightapi import LightApi

    engine = create_engine("sqlite:///app.db")
    app = LightApi(engine=engine)
    ```

=== "Async (PostgreSQL / SQLite)"

    ```python
    from sqlalchemy.ext.asyncio import create_async_engine
    from lightapi import LightApi

    engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
    app = LightApi(engine=engine)
    ```

When an `AsyncEngine` is detected, every built-in CRUD operation automatically uses async sessions.

## YAML Bootstrap

`LightApi.from_config()` loads a YAML file validated by Pydantic v2 and returns
a fully configured `LightApi` instance. Two formats are supported.

**Declarative format** — define fields and `Meta` options directly in YAML, no
Python `RestEndpoint` classes required:

```yaml
# lightapi.yaml
database:
  url: "${DATABASE_URL}"      # ${VAR} env substitution

cors_origins:
  - "https://myapp.com"

defaults:
  authentication:
    backend: JWTAuthentication
    permission: IsAuthenticated

endpoints:
  - route: /users
    fields:
      username: { type: str, min_length: 3 }
      email:    { type: str }
    meta:
      methods: [GET, POST, PUT, DELETE]

  - route: /posts
    fields:
      title:   { type: str }
      content: { type: str }
    meta:
      methods: [GET, POST]
      authentication:
        permission: AllowAny   # override the global default
```

```python
from lightapi import LightApi

app = LightApi.from_config("lightapi.yaml")
app.run()
```

See [Configuration](configuration.md) for the complete schema reference.

## Stack

| Component | Library |
|-----------|---------|
| HTTP server | Uvicorn |
| ASGI framework | Starlette |
| ORM | SQLAlchemy 2.x |
| Validation | Pydantic v2 |
| JWT | PyJWT |
| Caching | Redis (optional) |
| Async DB drivers | asyncpg, aiosqlite (optional) |

## Next Steps

- **[Installation](installation.md)** — install LightAPI and its optional extras
- **[Quickstart](quickstart.md)** — build a working API in under 5 minutes
- **[First Steps](first-steps.md)** — project layout and step-by-step walkthrough
