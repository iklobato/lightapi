---
title: Endpoint Classes
---

# Endpoint Classes

> Compact reference. See [REST API Reference](../api-reference/rest.md) for full documentation.

## `RestEndpoint`

```python
from lightapi import RestEndpoint, Field
```

A single class that is simultaneously an SQLAlchemy ORM model, a Pydantic v2 schema, and an HTTP handler. Fields are declared as annotated class attributes.

```python
from typing import Optional
from decimal import Decimal
from lightapi import RestEndpoint, Field

class ProductEndpoint(RestEndpoint):
    name:     str     = Field(min_length=1, max_length=200)
    price:    Decimal = Field(ge=0, decimal_places=2)
    category: str
    active:   bool    = Field(default=True)
    note:     Optional[str] = None
```

### Auto-injected columns

Every subclass automatically gets: `id` (PK), `created_at`, `updated_at`, `version`.

### HTTP method control

Inherit from `HttpMethod` mixins to restrict which verbs are exposed:

```python
from lightapi import RestEndpoint, HttpMethod

class ReadOnlyEndpoint(RestEndpoint, HttpMethod.GET):
    title: str
```

Available mixins: `HttpMethod.GET`, `HttpMethod.POST`, `HttpMethod.PUT`, `HttpMethod.PATCH`, `HttpMethod.DELETE`.

### `Meta` inner class

Control per-endpoint behaviour:

```python
from lightapi import (
    RestEndpoint, Field,
    Authentication, JWTAuthentication, IsAuthenticated,
    Filtering, FieldFilter, SearchFilter, OrderingFilter,
    Pagination, Serializer, Cache,
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
| `filtering` | `Filtering` | Filter backends and allowed fields |
| `pagination` | `Pagination` | Pagination style and page size |
| `serializer` | `Serializer` | Field visibility per verb |
| `cache` | `Cache` | Response caching TTL |
| `reflect` | `bool` | Reflect an existing table |
| `table` | `str` | Override the inferred table name |

### Built-in CRUD methods

| Method | HTTP | Description |
|--------|------|-------------|
| `list(request)` | `GET /path` | Return all rows (filtered/paginated if configured) |
| `retrieve(request, pk)` | `GET /path/{id}` | Return one row |
| `create(data)` | `POST /path` | Validate and insert a row |
| `update(data, pk, partial)` | `PUT/PATCH /path/{id}` | Update a row |
| `destroy(request, pk)` | `DELETE /path/{id}` | Delete a row |

Async counterparts: `_list_async`, `_retrieve_async`, `_create_async`, `_update_async`, `_destroy_async`.

### Method overrides

Override built-in methods to add custom logic:

```python
from starlette.requests import Request
from starlette.responses import JSONResponse

class PostEndpoint(RestEndpoint):
    title: str
    body: str

    def create(self, data: dict) -> JSONResponse:
        data["title"] = data["title"].strip()
        return super().create(data)

    async def _create_async(self, data: dict) -> JSONResponse:
        data["title"] = data["title"].strip()
        return await super()._create_async(data)
```

### Background tasks

```python
def send_email(to: str) -> None:
    ...

class UserEndpoint(RestEndpoint):
    email: str

    def create(self, data: dict):
        response = super().create(data)
        self.background(send_email, data["email"])
        return response
```
