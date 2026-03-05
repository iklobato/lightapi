---
title: Validation Examples
---

# Validation Examples

LightAPI validates request bodies automatically using Pydantic v2. Declare constraints directly on field annotations — no separate validator class needed.

## Basic constraints

```python
from typing import Optional
from decimal import Decimal
from lightapi import RestEndpoint, Field

class ProductEndpoint(RestEndpoint):
    name:        str            = Field(min_length=1, max_length=100)
    slug:        str            = Field(min_length=1, max_length=100, unique=True, index=True)
    price:       Decimal        = Field(gt=0, decimal_places=2)
    stock:       int            = Field(ge=0, default=0)
    description: Optional[str] = Field(None, max_length=2000)
```

## Supported constraints

| Constraint | Types | Description |
|------------|-------|-------------|
| `min_length` | `str` | Minimum string length |
| `max_length` | `str` | Maximum string length |
| `pattern` | `str` | Regex pattern |
| `gt` / `ge` | `int`, `float`, `Decimal` | Greater than / greater than or equal |
| `lt` / `le` | `int`, `float`, `Decimal` | Less than / less than or equal |
| `default` | any | Default value (skips required validation) |

All standard [Pydantic v2 field constraints](https://docs.pydantic.dev/latest/concepts/fields/) are supported.

## Validation error response

On validation failure, LightAPI returns `422 Unprocessable Entity`:

```bash
curl -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -d '{"name": "", "price": -5}'
```

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

## Email / pattern validation

```python
class UserEndpoint(RestEndpoint):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email:    str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
```

## Optional fields with defaults

```python
from typing import Optional

class CommentEndpoint(RestEndpoint):
    body:     str           = Field(min_length=1, max_length=2000)
    approved: bool          = Field(default=False)
    score:    Optional[int] = None    # accepts null in POST body
```

## Schema control with `Serializer`

Restrict which fields clients can write or read:

```python
from lightapi import RestEndpoint, Field, Serializer

class UserEndpoint(RestEndpoint):
    username:        str = Field(min_length=3, unique=True)
    email:           str = Field(unique=True)
    hashed_password: str

    class Meta:
        serializer = Serializer(
            read=["id", "username", "email", "created_at"],
            write=["username", "email", "hashed_password"],
        )
```

`hashed_password` is accepted on `POST`/`PUT`/`PATCH` but never returned in responses.

## Custom validation via method override

```python
from starlette.responses import JSONResponse

class OrderEndpoint(RestEndpoint):
    item:     str
    quantity: int = Field(ge=1, le=100)

    def create(self, data: dict) -> JSONResponse:
        if data.get("quantity", 0) > 50 and data.get("item") == "premium":
            return JSONResponse(
                {"detail": "Premium items limited to 50 per order"},
                status_code=422,
            )
        return super().create(data)
```

## Read vs. write schemas

LightAPI auto-generates two schemas per endpoint:

| Schema | Fields | Used for |
|--------|--------|---------|
| Write | All declared fields + their constraints | `POST`, `PUT`, `PATCH` validation |
| Read | All declared + auto-injected columns | Response serialisation |

Auto-injected columns (`id`, `created_at`, `updated_at`, `version`) are always present in read responses and always excluded from write input.
