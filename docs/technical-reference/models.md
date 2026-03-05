---
title: Database Models
---

# Database Models

> Compact reference. See [API Reference — Database](../api-reference/database.md) and [Tutorial — Database](../tutorial/database.md) for full documentation.

## `RestEndpoint` as a model

In LightAPI v2, there is no separate `Base` or declarative base. Each `RestEndpoint` subclass is itself the model, schema, and handler.

```python
from typing import Optional
from lightapi import RestEndpoint, Field

class UserEndpoint(RestEndpoint):
    username: str = Field(min_length=3, max_length=50, unique=True, index=True)
    email:    str = Field(unique=True)
    bio:      Optional[str] = None
```

### Auto-injected columns

| Column | Type | Notes |
|--------|------|-------|
| `id` | `Integer` PK | Auto-increment, never writeable by clients |
| `created_at` | `DateTime` | Set on insert |
| `updated_at` | `DateTime` | Set on insert and update |
| `version` | `Integer` | Optimistic locking counter, starts at 1 |

### Type map

| Python annotation | SQLAlchemy column |
|------------------|-------------------|
| `str` | `String` |
| `int` | `Integer` |
| `float` | `Float` |
| `bool` | `Boolean` |
| `datetime.datetime` | `DateTime` |
| `Decimal` | `Numeric` |
| `UUID` | `UUID` |
| `Optional[T]` | Same column, `nullable=True` |

### `Field()` kwargs

| Kwarg | Effect |
|-------|--------|
| `unique=True` | `UNIQUE` constraint |
| `index=True` | Database index |
| `foreign_key="table.col"` | `ForeignKey` reference |
| `decimal_places=N` | `Numeric(scale=N)` |
| `exclude=True` | Schema-only field, no DB column |

Standard Pydantic constraints (`min_length`, `max_length`, `gt`, `ge`, etc.) also work and are applied to input validation.

## Session helpers

```python
from lightapi import get_sync_session, get_async_session
```

Use these in custom `queryset` overrides or service code:

```python
from lightapi import RestEndpoint, get_sync_session

class ReportEndpoint(RestEndpoint):
    label: str

    def queryset(self, request):
        from sqlalchemy import select
        engine = self._get_engine()
        with get_sync_session(engine) as session:
            return select(type(self)._model_class)
```

## Reflection

Map an existing database table without declaring fields:

```python
class LegacyOrderEndpoint(RestEndpoint):
    class Meta:
        reflect = True
        table = "orders"   # explicit table name (optional)
```

For async engines, reflection uses `conn.run_sync(metadata.reflect)` internally.

## Table naming

The table name is inferred by stripping the `Endpoint` suffix (if present) and lowercasing: `UserEndpoint` → `users`, `ProductEndpoint` → `products`. Override with `Meta.table`.
