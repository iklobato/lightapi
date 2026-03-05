---
title: Exceptions API Reference
description: Built-in exceptions in LightAPI v2
---

# Exceptions API Reference

LightAPI v2 defines two framework-level exceptions. All other error responses use standard Starlette/HTTP status codes.

## `ConfigurationError`

```python
from lightapi import ConfigurationError
# or: from lightapi.exceptions import ConfigurationError
```

Raised at startup when a `RestEndpoint` or `LightApi` configuration is invalid.

**Common causes:**

- A field annotation uses a type not in the type map and `exclude=True` is not set.
- `Meta.serializer` has both `fields` and `read`/`write` set (mutually exclusive).
- `Meta.pagination` uses an invalid `style` value or `page_size < 1`.
- `Meta.cache` has `ttl < 1`.
- An async engine is used without the `lightapi[async]` extras installed.
- A YAML `database_url` references an unset environment variable.

```python
from lightapi import RestEndpoint, ConfigurationError

try:
    class BadEndpoint(RestEndpoint):
        data: list   # list is not in the type map
except ConfigurationError as e:
    print(e)
# RestEndpoint 'BadEndpoint': annotation 'list' on field 'data' is not in the type map.
```

## `SerializationError`

```python
from lightapi import SerializationError
# or: from lightapi.exceptions import SerializationError
```

Raised when a database row cannot be converted to a serialisable dict. This typically happens when a column value has an unexpected type.

## HTTP-level errors

For HTTP errors returned to clients, LightAPI uses standard Starlette responses:

| Situation | Status |
|-----------|--------|
| Resource not found | `404 Not Found` |
| Version conflict (optimistic locking) | `409 Conflict` |
| Validation failure | `422 Unprocessable Entity` |
| Unauthenticated | `401 Unauthorized` |
| Insufficient permission | `403 Forbidden` |
| Method not allowed | `405 Method Not Allowed` |
| Server error | `500 Internal Server Error` |

To return custom error responses from method overrides, use `starlette.responses.JSONResponse`:

```python
from starlette.responses import JSONResponse

class MyEndpoint(RestEndpoint):
    name: str

    async def post(self, request):
        data = await request.json()
        if not data.get("name"):
            return JSONResponse({"detail": "name is required"}, status_code=422)
        return await self._create_async(data)
```
