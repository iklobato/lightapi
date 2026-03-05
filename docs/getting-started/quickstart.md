---
title: Quickstart Guide
description: Create your first LightAPI v2 application in 5 minutes
---

# Quickstart Guide

Get a full CRUD REST API running in under 5 minutes with LightAPI v2.

## Prerequisites

- Python 3.10+
- `uv` or `pip`

```bash
uv pip install lightapi
# or: pip install lightapi
```

---

## Method 1: Python Code (Recommended for v2)

In LightAPI v2, a single annotated class is your ORM model, your Pydantic schema, **and** your HTTP endpoint.

### Step 1: Define an endpoint

```python
# main.py
from sqlalchemy import create_engine
from lightapi import LightApi, RestEndpoint, Field
from typing import Optional

class BookEndpoint(RestEndpoint):
    title: str = Field(min_length=1, description="Book title")
    author: str = Field(min_length=1, description="Author name")
    year: Optional[int] = None

engine = create_engine("sqlite:///books.db")
app = LightApi(engine=engine)
app.register({"/books": BookEndpoint})

if __name__ == "__main__":
    app.run()
```

### Step 2: Run it

```bash
python main.py
```

### Step 3: Try the API

```bash
# Create a book
curl -X POST http://localhost:8000/books \
  -H "Content-Type: application/json" \
  -d '{"title": "Clean Code", "author": "Robert Martin", "year": 2008}'
# → 201 {"id": 1, "title": "Clean Code", "author": "Robert Martin", "year": 2008, "version": 1, ...}

# List all books
curl http://localhost:8000/books
# → {"results": [{...}]}

# Get one book
curl http://localhost:8000/books/1

# Update (version field required for optimistic locking)
curl -X PUT http://localhost:8000/books/1 \
  -H "Content-Type: application/json" \
  -d '{"title": "Clean Code (Revised)", "author": "Robert Martin", "year": 2008, "version": 1}'
# → 200 {"id": 1, "version": 2, ...}

# Delete
curl -X DELETE http://localhost:8000/books/1
# → 204 No Content
```

---

## Method 2: YAML Configuration

LightAPI supports two YAML styles. The **declarative format** lets you define
fields and `Meta` options entirely in YAML — no Python classes needed:

```yaml
# lightapi.yaml
database:
  url: "${DATABASE_URL}"    # ${VAR} env-var substitution
cors_origins:
  - "http://localhost:3000"

defaults:
  pagination:
    style: page_number
    page_size: 25

endpoints:
  - route: /books
    fields:
      title:  { type: str, max_length: 255 }
      author: { type: str }
      year:   { type: int, optional: true }
    meta:
      methods: [GET, POST, PUT, DELETE]
      filtering:
        fields:   [author]
        ordering: [year, title]
```

```python
from lightapi import LightApi

app = LightApi.from_config("lightapi.yaml")
app.run()
```

See the [Configuration Guide](configuration.md) for the full YAML schema reference.

---

## Auto-generated columns

Every `RestEndpoint` automatically gets these columns — no need to declare them:

| Column | Type | Description |
|--------|------|-------------|
| `id` | `INTEGER` PK | Auto-increment primary key |
| `created_at` | `DATETIME` | Set on insert |
| `updated_at` | `DATETIME` | Updated on every write |
| `version` | `INTEGER` | Optimistic locking counter (starts at 1) |

---

---

## Async Quick Start (PostgreSQL)

Swap `create_engine` for `create_async_engine` — everything else is unchanged:

```bash
uv add "lightapi[async]"
```

```python
# main_async.py
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request
from lightapi import LightApi, RestEndpoint, Field
from lightapi.auth import AllowAny
from lightapi.config import Authentication

class BookEndpoint(RestEndpoint):
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    year: Optional[int] = None

    class Meta:
        authentication = Authentication(permission=AllowAny)

    async def queryset(self, request: Request):
        from sqlalchemy import select
        return select(type(self)._model_class)

engine = create_async_engine(
    "postgresql+asyncpg://postgres:postgres@localhost:5432/mydb"
)
app = LightApi(engine=engine)
app.register({"/books": BookEndpoint})

if __name__ == "__main__":
    app.run()
```

The API surface is identical — the same `curl` commands work unchanged.

See [Async Support](../advanced/async.md) for background tasks, async middleware, and testing.

---

## What's next?

- [Async Support](../advanced/async.md) — async engine, queryset, background tasks
- [Authentication](../advanced/authentication.md) — JWT + permission classes
- [Filtering & Ordering](../advanced/filtering.md) — `Meta.filtering`
- [Pagination](../advanced/pagination.md) — page-number and cursor styles
- [Middleware](../advanced/middleware.md) — sync and async `Middleware.process`
- [Caching](../advanced/caching.md) — `Meta.cache = Cache(ttl=N)`
