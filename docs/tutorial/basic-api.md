---
title: Building Your First API
description: Step-by-step tutorial for creating a complete REST API with LightAPI v2
---

# Building Your First API

This tutorial builds a small blog API from scratch: articles with a title, body, and published flag. By the end you will have a fully working CRUD API with filtering, pagination, and JWT authentication.

## Prerequisites

```bash
uv add lightapi
# or: pip install lightapi
```

## Step 1 — Define the endpoint

Create `blog/endpoints.py`:

```python
from typing import Optional
from lightapi import (
    RestEndpoint, Field,
    Authentication, JWTAuthentication, IsAuthenticated, AllowAny,
    Filtering, Pagination, Serializer,
    FieldFilter, SearchFilter, OrderingFilter,
)

class ArticleEndpoint(RestEndpoint):
    title: str = Field(min_length=1, max_length=200)
    body: str
    published: Optional[bool] = Field(None, default=False)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission={
                "GET": AllowAny,
                "POST": IsAuthenticated,
                "PUT": IsAuthenticated,
                "PATCH": IsAuthenticated,
                "DELETE": IsAuthenticated,
            },
        )
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["published"],
            search=["title", "body"],
            ordering=["title", "created_at"],
        )
        pagination = Pagination(style="page_number", page_size=10)
        serializer = Serializer(
            read=["id", "title", "published", "created_at"],
            write=["title", "body", "published"],
        )
```

## Step 2 — Wire up the application

Create `blog/main.py`:

```python
import os
from sqlalchemy import create_engine
from lightapi import LightApi
from blog.endpoints import ArticleEndpoint

os.environ.setdefault("LIGHTAPI_JWT_SECRET", "dev-secret-change-me")

engine = create_engine(os.environ.get("DATABASE_URL", "sqlite:///blog.db"))

app = LightApi(engine=engine)
app.register({"/articles": ArticleEndpoint})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

## Step 3 — Run the server

```bash
python blog/main.py
```

LightAPI creates the `articles` table automatically on first run.

## Step 4 — Create a token

LightAPI does not include a login endpoint. Generate a token in the Python shell:

```python
import jwt, datetime, os
os.environ["LIGHTAPI_JWT_SECRET"] = "dev-secret-change-me"
token = jwt.encode(
    {"sub": "1", "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
    "dev-secret-change-me",
    algorithm="HS256",
)
print(token)
```

## Step 5 — Interact with the API

```bash
TOKEN="<paste-token-here>"

# Create an article (requires auth)
curl -X POST http://localhost:8000/articles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Hello LightAPI", "body": "This is my first article.", "published": true}'
# → 201 {"id": 1, "title": "Hello LightAPI", "published": true, "created_at": "..."}

# List articles (public)
curl http://localhost:8000/articles
# → {"count": 1, "next": null, "previous": null, "results": [...]}

# Filter by published
curl "http://localhost:8000/articles?published=true"

# Full-text search
curl "http://localhost:8000/articles?search=LightAPI"

# Order by newest first
curl "http://localhost:8000/articles?ordering=-created_at"

# Get a single article
curl http://localhost:8000/articles/1
# → {"id": 1, "title": "Hello LightAPI", "published": true, "created_at": "..."}

# Update (requires current version)
curl -X PATCH http://localhost:8000/articles/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"published": false, "version": 1}'
# → 200 {"id": 1, ..., "version": 2}

# Delete
curl -X DELETE http://localhost:8000/articles/1 \
  -H "Authorization: Bearer $TOKEN"
# → 204 No Content
```

## What you built

| Feature | Provided by |
|---------|-------------|
| Auto CRUD routes | `RestEndpoint` metaclass |
| `articles` table creation | `app.register()` |
| JWT auth (public reads, auth writes) | `Meta.authentication` with per-method dict |
| Exact-match filter `?published=` | `FieldFilter` in `Meta.filtering` |
| Full-text search `?search=` | `SearchFilter` |
| Sort `?ordering=` | `OrderingFilter` |
| Page-number pagination | `Meta.pagination` |
| Read-only serializer fields | `Meta.serializer` |
| Optimistic locking via `version` | Built-in |
| Pydantic v2 validation | `Field(min_length=...)` |

## Next Steps

- [Async Support](../advanced/async.md) — swap to `create_async_engine` for async I/O
- [Middleware](../advanced/middleware.md) — add request logging, rate limiting, etc.
- [Background Tasks](../advanced/async.md#background-tasks) — fire-and-forget after the response
- [Reflection](../api-reference/rest.md#reflection) — point at an existing database table
