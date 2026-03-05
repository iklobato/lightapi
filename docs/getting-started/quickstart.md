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

Configure endpoints without Python code using a YAML file that points to your `RestEndpoint` classes.

```yaml
# lightapi.yaml
database_url: "${DATABASE_URL}"   # env var substitution
cors_origins:
  - "http://localhost:3000"
endpoints:
  - path: /books
    class: myapp.endpoints.BookEndpoint
```

```python
from lightapi import LightApi

app = LightApi.from_config("lightapi.yaml")
app.run()
```

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

## What's next?

- [Authentication](../advanced/authentication.md) — JWT + permission classes
- [Filtering & Ordering](../advanced/filtering.md) — `Meta.filtering`
- [Pagination](../advanced/pagination.md) — page-number and cursor styles
- [Serializer](../advanced/serializer.md) — per-verb field projection
- [Middleware](../advanced/middleware.md) — `Middleware.process(request, response)`
- [Caching](../advanced/caching.md) — `Meta.cache = Cache(ttl=N)`
