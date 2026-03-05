---
title: Caching Implementation
---

# Caching Implementation

> Compact reference. See [Advanced — Caching](../advanced/caching.md) and [API Reference — Cache](../api-reference/cache.md) for full documentation.

## `Cache` config object

```python
from lightapi import Cache

Cache(ttl: int, vary_on: list[str] | None = None)
```

Enable response caching via `Meta.cache`:

```python
from lightapi import RestEndpoint, Cache

class ProductEndpoint(RestEndpoint):
    name: str
    price: float

    class Meta:
        cache = Cache(ttl=300)   # 5-minute cache on GET responses
```

- `ttl`: seconds to cache a response. Must be ≥ 1.
- `vary_on`: list of query parameter names included in the cache key. Default: all query params.

## Cache key

The key is derived from the endpoint class name and the full request URL (path + query string). When `vary_on` is set, only those query parameters are included.

## `RedisCache` backend

```python
from lightapi import RedisCache

RedisCache(host="localhost", port=6379, db=0)
```

Used internally by the framework. Serialises values as JSON.

| Method | Signature | Description |
|--------|-----------|-------------|
| `get(key)` | `str → dict \| None` | Returns cached dict or `None` on miss/error. |
| `set(key, value, timeout)` | `str, dict, int → bool` | Stores value; returns `False` on error. |

## `BaseCache`

Extend to implement a custom cache backend:

```python
from lightapi.cache import BaseCache
from typing import Any, Dict, Optional

class MyCache(BaseCache):
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        ...

    def set(self, key: str, value: Dict[str, Any], timeout: int = 300) -> bool:
        ...
```

## Redis connection

The Redis URL is read from `LIGHTAPI_REDIS_URL` (default: `redis://localhost:6379/0`). Connection errors are silently ignored — if Redis is unreachable, caching is skipped and a `RuntimeWarning` is emitted at startup.

## Invalidation

Write operations (`POST`, `PUT`, `PATCH`, `DELETE`) automatically invalidate all cached keys for the endpoint prefix. No manual invalidation is needed.
