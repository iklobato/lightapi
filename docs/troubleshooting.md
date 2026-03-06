---
title: Troubleshooting Guide
description: Common issues and solutions for LightAPI v2
---

# Troubleshooting Guide

## Runtime Errors

### `ConfigurationError` at startup

**Cause:** Invalid `RestEndpoint` or `LightApi` configuration detected before any request is served.

**Common causes:**

- Field annotation type not in the type map (use `str`, `int`, `float`, `bool`, `datetime`, `Decimal`, `UUID`)
- `Meta.pagination` uses an invalid `style` value or `page_size < 1`
- `Meta.cache` has `ttl < 1`
- Async engine used without `lightapi[async]` installed
- YAML `${VAR}` references an unset environment variable

```python
# ❌ Wrong — list is not in the type map
class BadEndpoint(RestEndpoint):
    tags: list

# ✅ Fix — use a supported type; store as JSON string if needed
class GoodEndpoint(RestEndpoint):
    tags: str = Field(default="")
```

### `401 Unauthorized` on all requests

**Cause:** JWT authentication is enabled but the request is missing a valid token.

1. Ensure `LIGHTAPI_JWT_SECRET` is set and matches the secret used to sign tokens.
2. Send `Authorization: Bearer <token>` with every request.
3. Generate a token:

```python
import os
os.environ["LIGHTAPI_JWT_SECRET"] = "your-secret"
from lightapi.auth import JWTAuthentication
auth = JWTAuthentication()
token = auth.generate_token({"sub": "1", "is_admin": False})
print(token)
```

### `422 Unprocessable Entity`

Pydantic validation failed. Check the response body for the specific failing field:

```json
{
  "detail": [
    {"type": "string_too_short", "loc": ["name"], "msg": "String should have at least 1 character", ...}
  ]
}
```

### `405 Method Not Allowed`

The endpoint was registered with `HttpMethod` mixins that exclude the attempted verb:

```python
# Only GET is allowed — POST returns 405
class ReadOnlyEndpoint(RestEndpoint, HttpMethod.GET):
    title: str
```

Remove the mixin restriction or add the required method mixin.

## Configuration Issues

### JWT secret not configured

```
ValueError: JWT secret key not configured. Set LIGHTAPI_JWT_SECRET environment variable.
```

```bash
export LIGHTAPI_JWT_SECRET="$(openssl rand -hex 32)"
```

### Port already in use

```bash
lsof -ti:8000 | xargs kill -9
# or use a different port
app.run(port=8001)
```

### CORS preflight blocked

Pass allowed origins to `LightApi`:

```python
app = LightApi(engine=engine, cors_origins=["https://myapp.com", "http://localhost:3000"])
```

Use `["*"]` for development only.

## Database Issues

### Table does not exist (`Meta.reflect`)

```
ConfigurationError: Meta.reflect is set on 'MyEndpoint' but table 'myendpoints' does not exist.
```

Specify the correct table name:

```python
class MyEndpoint(RestEndpoint):
    class Meta:
        reflect = True
        table = "correct_table_name"
```

### SQLAlchemy URL format

```python
# SQLite
"sqlite:///app.db"
"sqlite:///./app.db"

# PostgreSQL (sync)
"postgresql+psycopg2://user:pass@localhost:5432/mydb"

# PostgreSQL (async)
"postgresql+asyncpg://user:pass@localhost:5432/mydb"

# MySQL
"mysql+pymysql://user:pass@localhost:3306/mydb"
```

### Async engine without async extras

```
ConfigurationError: Async SQLAlchemy is not installed. Run: uv add "lightapi[async]"
```

```bash
uv add "lightapi[async]"
```

## Middleware Issues

### Middleware registration

Register middleware via `LightApi`, not `app.add_middleware()` (which does not exist in v2):

```python
# ✅ v2 — pass to constructor
from lightapi import LightApi
from lightapi.core import Middleware

class MyMiddleware(Middleware):
    def process(self, request, response):
        return response

app = LightApi(engine=engine, middlewares=[MyMiddleware])
```

### Middleware `process()` signature

The `process` method takes **two** arguments: `request` and `response`. `response` is `None` during pre-processing:

```python
class MyMiddleware(Middleware):
    def process(self, request, response):
        if response is None:
            # pre-processing
            return None
        # post-processing
        return response
```

## Caching Issues

### Redis unreachable

LightAPI emits a `RuntimeWarning` if Redis cannot be reached at startup and silently disables caching. Set `LIGHTAPI_REDIS_URL` to the correct URL:

```bash
export LIGHTAPI_REDIS_URL="redis://localhost:6379/0"
redis-server   # ensure Redis is running
```

Verify:

```python
import redis
r = redis.from_url("redis://localhost:6379/0")
print(r.ping())  # True
```

## Performance Tips

### Indexes

Declare indexes on frequently queried columns:

```python
class UserEndpoint(RestEndpoint):
    email:    str = Field(unique=True, index=True)
    username: str = Field(index=True)
```

### Use async for high-concurrency workloads

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/mydb")
app = LightApi(engine=engine)
```

### Filtering instead of post-processing

Use `Meta.filtering` rather than filtering results in Python — let the database do the work.

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `LIGHTAPI_DATABASE_URL` | Database URL when no engine is given | — (required) |
| `LIGHTAPI_JWT_SECRET` | JWT signing secret | — (required) |
| `LIGHTAPI_REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |

## Minimal working example

```python
import os
from sqlalchemy import create_engine
from lightapi import LightApi, RestEndpoint, Field, Authentication, JWTAuthentication, IsAuthenticated

os.environ["LIGHTAPI_JWT_SECRET"] = "dev-secret"

class ItemEndpoint(RestEndpoint):
    name:  str   = Field(min_length=1)
    price: float = Field(ge=0)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
        )

engine = create_engine("sqlite:///app.db")
app = LightApi(engine=engine, cors_origins=["*"])
app.register({"/items": ItemEndpoint})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```
