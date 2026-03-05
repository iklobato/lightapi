---
title: Validation API Reference
description: Pydantic v2 field validation and schema generation in LightAPI v2
---

# Validation API Reference

LightAPI v2 uses **Pydantic v2** for all request body validation. There is no separate validator class — constraints are declared directly on field annotations.

## How validation works

1. On `POST`, `PUT`, or `PATCH`, LightAPI parses the request body as JSON.
2. It validates the data against the auto-generated Pydantic write schema.
3. On failure, it returns `422 Unprocessable Entity` with the Pydantic error detail.
4. On success, it proceeds with the database operation.

## Declaring constraints

```python
from typing import Optional
from decimal import Decimal
from lightapi import RestEndpoint, Field

class ProductEndpoint(RestEndpoint):
    name: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(gt=0, decimal_places=2)
    stock: int = Field(ge=0, default=0)
    email: Optional[str] = Field(None, pattern=r"^[^@]+@[^@]+\.[^@]+$")
```

All [Pydantic v2 field constraints](https://docs.pydantic.dev/latest/concepts/fields/) work directly.

## Error response format

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
      "input": -5.0,
      "ctx": {"gt": 0}
    }
  ]
}
```

## Read vs. write schemas

LightAPI generates two Pydantic schemas per endpoint:

| Schema | Fields included | Used for |
|--------|----------------|----------|
| Write (create) | All declared fields with their constraints | `POST` / `PUT` / `PATCH` validation |
| Read | All columns including auto-injected ones | Response serialisation |

Control which fields appear using `Meta.serializer`:

```python
from lightapi import RestEndpoint, Serializer

class UserEndpoint(RestEndpoint):
    username: str
    email: str
    hashed_password: str

    class Meta:
        serializer = Serializer(
            read=["id", "username", "email", "created_at"],
            write=["username", "email", "hashed_password"],
        )
```

## `Serializer`

```python
from lightapi import Serializer

Serializer(
    fields: list[str] | None = None,  # unified read+write whitelist
    read: list[str] | None = None,    # read-only whitelist
    write: list[str] | None = None,   # write-only whitelist
)
```

`fields` and `read`/`write` are mutually exclusive — passing both raises `ConfigurationError`.

## Custom validation via method overrides

For domain-level validation that goes beyond field constraints, override the HTTP method:

```python
import json
from starlette.responses import JSONResponse
from lightapi import RestEndpoint

class OrderEndpoint(RestEndpoint):
    item_id: int
    quantity: int

    async def post(self, request):
        data = json.loads(await request.body())
        # Custom domain rule
        if data.get("quantity", 0) > 1000:
            return JSONResponse(
                {"detail": "Quantity cannot exceed 1000"},
                status_code=422,
            )
        return await self._create_async(data)
```

## Optimistic locking validation

`PUT` and `PATCH` requests must include the current `version` value. The framework validates it against the database row:

- If `version` matches: update succeeds, `version` is incremented.
- If `version` is missing or mismatched: returns `409 Conflict`.
- If the record is not found: returns `404 Not Found`.

## `SchemaFactory` (internal)

LightAPI uses `SchemaFactory` to programmatically create Pydantic models from SQLAlchemy column metadata. You do not need to interact with it directly, but it is available for advanced use:

```python
from lightapi import SchemaFactory

schema = SchemaFactory.create_schema(
    name="MyModel",
    columns={"title": (str, ...)},
)
```
