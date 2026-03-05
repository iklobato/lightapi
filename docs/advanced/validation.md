---
title: Validation
description: Automatic request validation via Pydantic v2 field constraints
---

# Validation

LightAPI validates request bodies automatically using Pydantic v2. Constraints are declared directly on field annotations via `Field(...)` and are enforced on every `POST`, `PUT`, and `PATCH` request.

## Field constraints

```python
from typing import Optional
from decimal import Decimal
from lightapi import RestEndpoint, Field

class ProductEndpoint(RestEndpoint):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100, unique=True, index=True)
    price: Decimal = Field(gt=0, decimal_places=2)
    stock: int = Field(ge=0, default=0)
    description: Optional[str] = Field(None, max_length=2000)
```

All standard [Pydantic v2 field constraints](https://docs.pydantic.dev/latest/concepts/fields/) are supported.

## Validation errors

When validation fails, LightAPI returns `422 Unprocessable Entity` with a detailed Pydantic error body:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["name"],
      "msg": "String should have at least 1 character",
      "input": "",
      "ctx": {"min_length": 1}
    },
    {
      "type": "greater_than",
      "loc": ["price"],
      "msg": "Input should be greater than 0",
      "input": -5,
      "ctx": {"gt": 0}
    }
  ]
}
```

## Supported field types

| Python type | SQLAlchemy column | Notes |
|-------------|-------------------|-------|
| `str` | `String` | |
| `int` | `Integer` | |
| `float` | `Float` | |
| `bool` | `Boolean` | |
| `Decimal` | `Numeric` | Use `decimal_places=N` extra kwarg |
| `datetime.datetime` | `DateTime` | |
| `Optional[T]` | nullable column | Makes the column nullable |

## `Field()` extra kwargs

Beyond standard Pydantic constraints, LightAPI adds extra kwargs processed by the metaclass:

| Kwarg | Type | Description |
|-------|------|-------------|
| `unique=True` | bool | Adds a `UNIQUE` constraint to the column. |
| `index=True` | bool | Creates a database index on the column. |
| `foreign_key="table.col"` | str | Creates a foreign key reference. |
| `decimal_places=N` | int | Precision for `Decimal` columns (default: 10). |
| `exclude=True` | bool | Skips column creation entirely — field exists only on the schema. |
| `default=<value>` | any | Sets both the Pydantic default and the SQLAlchemy column default. |

## Custom validation via method overrides

Override `post`, `put`, or `patch` to add domain-level validation:

```python
import json
from lightapi import RestEndpoint, Field

class UserEndpoint(RestEndpoint):
    username: str = Field(min_length=3, max_length=50)
    email: str

    async def post(self, request):
        data = json.loads(await request.body())
        if not data.get("email", "").endswith("@mycompany.com"):
            from starlette.responses import JSONResponse
            return JSONResponse(
                {"detail": "Only @mycompany.com emails are allowed"},
                status_code=422,
            )
        return await self._create_async(data)
```

## Auto-injected columns

These columns are always present and never need to be declared:

| Column | Type | Notes |
|--------|------|-------|
| `id` | `Integer` (PK, autoincrement) | Never writeable |
| `created_at` | `DateTime` | Set on insert |
| `updated_at` | `DateTime` | Updated on every write |
| `version` | `Integer` | Optimistic locking counter — must be included in PUT/PATCH bodies |

## Optimistic locking

`version` prevents lost updates. Every `PUT` and `PATCH` request **must** include the current `version` value. If it doesn't match the database, the request returns `409 Conflict`.

```bash
# Create
curl -X POST /items -d '{"name": "Widget"}' -H "Content-Type: application/json"
# → 201 {"id": 1, "name": "Widget", "version": 1, ...}

# Update — include current version
curl -X PUT /items/1 -d '{"name": "Widget Pro", "version": 1}' -H "Content-Type: application/json"
# → 200 {"id": 1, "name": "Widget Pro", "version": 2, ...}

# Stale update — wrong version
curl -X PUT /items/1 -d '{"name": "Widget Max", "version": 1}' -H "Content-Type: application/json"
# → 409 {"detail": "Version conflict"}
```

## Serializer and read-only fields

Use `Meta.serializer` to control which fields appear in responses (read) vs. what is accepted in request bodies (write):

```python
from lightapi import RestEndpoint, Serializer

class ProfileEndpoint(RestEndpoint):
    username: str
    email: str
    hashed_password: str = Field(exclude=True)  # never in schema

    class Meta:
        serializer = Serializer(
            read=["id", "username", "email", "created_at"],
            write=["username", "email"],
        )
```

See [API Reference — REST](../api-reference/rest.md) for the full `Serializer` reference.
