---
title: Caching
description: Redis-backed response caching for list and detail endpoints
---

# Caching

LightAPI provides Redis-based response caching via the `Cache` Meta option. When enabled, the framework caches successful `GET` responses and returns the cached result on subsequent identical requests.

## Quick Start

```python
from lightapi import RestEndpoint, Cache, RedisCache

class ProductEndpoint(RestEndpoint):
    name: str
    price: float

    class Meta:
        cache = Cache(ttl=300)   # cache GET responses for 5 minutes
```

Install Redis and start it locally:

```bash
redis-server
```

## YAML configuration

Set `meta.cache` in a `lightapi.yaml` file to enable caching without writing Python:

```yaml
endpoints:
  - route: /products
    fields:
      name:  { type: str }
      price: { type: float, ge: 0 }
    meta:
      methods: [GET, POST, PUT, PATCH, DELETE]
      cache:
        ttl: 300   # cache GET responses for 5 minutes; writes auto-invalidate
```

```python
from lightapi import LightApi

app = LightApi.from_config("lightapi.yaml")
app.run()
```

## `Cache` constructor

```python
Cache(
    ttl: int,                    # seconds — required
    vary_on: list[str] | None = None,
)
```

| Parameter | Description |
|-----------|-------------|
| `ttl` | Cache time-to-live in seconds. Must be ≥ 1. |
| `vary_on` | List of query parameter names that are included in the cache key. |

## `RedisCache` backend

By default LightAPI uses `RedisCache` when `Meta.cache` is set. You can instantiate it explicitly to control the connection:

```python
from lightapi import RedisCache

cache_backend = RedisCache(host="localhost", port=6379, db=0)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | `"localhost"` | Redis server hostname. |
| `port` | `6379` | Redis server port. |
| `db` | `0` | Redis database index. |

## Cache key

The default cache key is built from:

- The endpoint class name
- The full request URL path and query string

When `vary_on` is set, only the listed query parameters contribute to the key. This lets you share cached pages across unrelated parameters.

```python
class ArticleEndpoint(RestEndpoint):
    title: str
    published: bool

    class Meta:
        cache = Cache(ttl=60, vary_on=["page", "page_size"])
```

## Cache invalidation

Write operations (`POST`, `PUT`, `PATCH`, `DELETE`) automatically invalidate all cached entries for that endpoint's key prefix. No manual invalidation is needed for the common case.

```bash
GET /posts?published=true   # cache miss → stored for 120 s (X-Cache: MISS)
GET /posts?published=true   # cache hit  → returned instantly (X-Cache: HIT)
POST /posts                 # write → all /posts cache keys invalidated
GET /posts?published=true   # cache miss again → re-fetched from DB
```

If you need finer-grained invalidation (e.g. invalidate only on specific fields changing), implement a custom `post()`/`put()` override that calls `invalidate_cache_prefix(...)` directly.

## Example with filtering and pagination

```python
from lightapi import (
    RestEndpoint, Field, Pagination, Filtering, Cache,
    FieldFilter, OrderingFilter,
)

class PostEndpoint(RestEndpoint):
    title: str
    published: bool = Field(default=False)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, OrderingFilter],
            fields=["published"],
            ordering=["created_at"],
        )
        pagination = Pagination(style="page_number", page_size=20)
        cache = Cache(ttl=120, vary_on=["page", "page_size", "published"])
```

```bash
GET /posts?published=true&page=1   # cache miss → stored for 120 s
GET /posts?published=true&page=1   # cache hit → instant return
GET /posts?published=true&page=2   # different key → cache miss
```

> **Tip:** Include all query parameters that affect the response in `vary_on`. If `vary_on` is omitted, the full query string is part of the cache key — each unique URL is cached separately.

## Custom cache backend

Implement `BaseCache` to use a different store:

```python
from lightapi.cache import BaseCache
from typing import Any

class InMemoryCache(BaseCache):
    _store: dict[str, Any] = {}

    def get(self, key: str):
        return self._store.get(key)

    def set(self, key: str, value: Any, timeout: int = 300) -> bool:
        self._store[key] = value
        return True
```

Pass it to `Cache` via the `backend` parameter (if your version supports it), or use it directly inside a custom `get()` override.

## Redis connection

Set the Redis URL via environment variable:

```bash
export LIGHTAPI_REDIS_URL="redis://localhost:6379/0"
```

The default is `redis://localhost:6379/0`. A `RuntimeWarning` is emitted at startup if Redis is unreachable; caching is silently skipped for the lifetime of the process.

## Production notes

- Run Redis with persistence (`appendonly yes`) if cached data is expensive to regenerate.
- Use Redis Cluster or Sentinel for high-availability deployments.
- Monitor Redis memory usage; set `maxmemory-policy allkeys-lru` to auto-evict stale entries.
