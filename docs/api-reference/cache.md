---
title: Cache API Reference
description: Cache and RedisCache classes in LightAPI v2
---

# Cache API Reference

## `Cache`

```python
from lightapi import Cache

Cache(
    ttl: int,                        # seconds — required
    vary_on: list[str] | None = None,
)
```

Enables response caching for `GET` list and detail endpoints. Configured via `Meta.cache`:

```python
from lightapi import RestEndpoint, Cache

class ProductEndpoint(RestEndpoint):
    name: str
    price: float

    class Meta:
        cache = Cache(ttl=300)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `ttl` | `int` | Cache lifetime in seconds. Must be ≥ 1. |
| `vary_on` | `list[str] \| None` | Query parameter names included in the cache key. |

Raises `ConfigurationError` if `ttl < 1`.

## `RedisCache`

```python
from lightapi import RedisCache

RedisCache(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
)
```

The built-in Redis cache backend. Serializes cached values as JSON.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | `"localhost"` | Redis server hostname |
| `port` | `6379` | Redis server port |
| `db` | `0` | Redis database index |

## `BaseCache`

Base class for custom cache backends:

```python
from lightapi.cache import BaseCache
from typing import Any, Dict, Optional

class MyCache(BaseCache):
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        ...

    def set(self, key: str, value: Dict[str, Any], timeout: int = 300) -> bool:
        ...
```

## Cache key

The default cache key includes the endpoint class name and the full request URL (path + query string). When `vary_on` is set, only the listed query parameters are included in the key.

## Notes

- Caching applies to `GET` requests only.
- Write operations (`POST`, `PUT`, `PATCH`, `DELETE`) do **not** automatically invalidate cached entries.
- Use a short `ttl` or implement manual Redis key invalidation for consistency.
