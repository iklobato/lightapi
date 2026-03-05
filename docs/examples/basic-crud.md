---
title: Basic CRUD Examples
---

# Basic CRUD Operations

Full Create, Read, Update, and Delete operations on a simple `Item` resource.

## Setup

```bash
uv add lightapi
```

## Endpoint definition

```python
# endpoints.py
from typing import Optional
from lightapi import RestEndpoint, Field

class ItemEndpoint(RestEndpoint):
    name:        str            = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    price:       float          = Field(ge=0)
    in_stock:    bool           = Field(default=True)
```

LightAPI auto-generates:

- Table `items` with columns `id`, `name`, `description`, `price`, `in_stock`, `created_at`, `updated_at`, `version`
- Routes: `GET /items`, `POST /items`, `GET /items/{id}`, `PUT /items/{id}`, `PATCH /items/{id}`, `DELETE /items/{id}`

## Application wiring

```python
# main.py
from sqlalchemy import create_engine
from lightapi import LightApi
from endpoints import ItemEndpoint

engine = create_engine("sqlite:///items.db")
app = LightApi(engine=engine)
app.register({"/items": ItemEndpoint})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

## CRUD walkthrough

### Create

```bash
curl -X POST http://localhost:8000/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Widget", "price": 9.99}'
```

```json
{"id": 1, "name": "Widget", "description": null, "price": 9.99, "in_stock": true, "version": 1, "created_at": "...", "updated_at": "..."}
```

### List

```bash
curl http://localhost:8000/items
```

```json
{"results": [{"id": 1, "name": "Widget", ...}]}
```

### Retrieve

```bash
curl http://localhost:8000/items/1
```

### Full update (PUT)

```bash
curl -X PUT http://localhost:8000/items/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "Widget v2", "price": 12.99, "version": 1}'
```

`version` is required on `PUT` and `PATCH` for optimistic locking. The response includes the incremented `version`.

### Partial update (PATCH)

```bash
curl -X PATCH http://localhost:8000/items/1 \
  -H "Content-Type: application/json" \
  -d '{"price": 8.99, "version": 2}'
```

### Delete

```bash
curl -X DELETE http://localhost:8000/items/1
```

Returns `204 No Content`.

## Validation errors

Sending an invalid payload returns `422 Unprocessable Entity`:

```bash
curl -X POST http://localhost:8000/items \
  -H "Content-Type: application/json" \
  -d '{"name": "", "price": -5}'
```

```json
{
  "detail": [
    {"type": "string_too_short", "loc": ["name"], "msg": "String should have at least 1 character", ...},
    {"type": "greater_than_equal", "loc": ["price"], "msg": "Input should be greater than or equal to 0", ...}
  ]
}
```

## Adding filtering and pagination

```python
from lightapi import (
    RestEndpoint, Field, Filtering, Pagination,
    FieldFilter, OrderingFilter,
)

class ItemEndpoint(RestEndpoint):
    name:     str   = Field(min_length=1, max_length=200)
    price:    float = Field(ge=0)
    in_stock: bool  = Field(default=True)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, OrderingFilter],
            fields=["in_stock"],
            ordering=["price", "name"],
        )
        pagination = Pagination(style="page_number", page_size=25)
```

```bash
GET /items?in_stock=true&ordering=-price&page=2
```
