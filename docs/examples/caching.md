---
title: Caching Examples
---

# Caching Examples

LightAPI caches successful `GET` responses in Redis. Write operations automatically invalidate the cache for the endpoint.

## Prerequisites

```bash
uv add lightapi redis-server
# or on macOS: brew install redis && redis-server
```

## Basic caching

```python
from sqlalchemy import create_engine
from lightapi import LightApi, RestEndpoint, Field, Cache

class ProductEndpoint(RestEndpoint):
    name:  str   = Field(min_length=1, max_length=200)
    price: float = Field(ge=0)

    class Meta:
        cache = Cache(ttl=300)   # cache GET responses for 5 minutes

engine = create_engine("sqlite:///products.db")
app = LightApi(engine=engine)
app.register({"/products": ProductEndpoint})
app.run()
```

## `Cache` constructor

```python
Cache(
    ttl: int,                    # seconds — required, must be ≥ 1
    vary_on: list[str] | None = None,
)
```

| Parameter | Description |
|-----------|-------------|
| `ttl` | How long to cache responses in seconds. |
| `vary_on` | Query params included in the cache key. Default: all params. |

## Varying the cache key by query param

```python
from lightapi import Filtering, FieldFilter

class ProductEndpoint(RestEndpoint):
    name:     str  = Field(min_length=1)
    category: str
    active:   bool = Field(default=True)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter],
            fields=["category", "active"],
        )
        cache = Cache(
            ttl=120,
            vary_on=["category"],  # separate cache entry per category
        )
```

## Redis connection

Set `LIGHTAPI_REDIS_URL` to override the default (`redis://localhost:6379/0`):

```bash
export LIGHTAPI_REDIS_URL="redis://:password@redis-host:6379/1"
```

If Redis is unreachable at startup, LightAPI emits a `RuntimeWarning` and disables caching silently — the application continues to work without cached responses.

## Cache invalidation

Cache entries for an endpoint are automatically deleted when any `POST`, `PUT`, `PATCH`, or `DELETE` request succeeds. No manual invalidation is needed.

## Combining cache with pagination

```python
from lightapi import Pagination

class ArticleEndpoint(RestEndpoint):
    title: str
    body:  str

    class Meta:
        pagination = Pagination(style="page_number", page_size=20)
        cache = Cache(ttl=60, vary_on=["page"])
```

Each page is cached separately because `page` is in `vary_on`.

## Custom Redis backend

You can instantiate `RedisCache` explicitly for custom connection options:

```python
from lightapi import RedisCache

cache = RedisCache(host="redis.internal", port=6380, db=2)
```

The `RedisCache` class is available for direct use in custom caching logic. For `Meta.cache`, LightAPI manages the backend automatically.
