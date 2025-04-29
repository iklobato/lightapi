---
title: Caching with Redis
---

LightAPI supports pluggable caching backends to improve performance by storing frequently accessed data. The built-in `RedisCache` provides a simple Redis-based cache.

## Enabling Caching

To enable caching on an endpoint, configure the `caching_class` and `caching_method_names` in the endpoint's `Configuration`:

```python
from lightapi.rest import RestEndpoint
from lightapi.cache import RedisCache

class TaskEndpoint(RestEndpoint):
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['get']  # cache GET responses

    async def get(self, request):
        # This method will cache its result
        tasks = await self.session.query(Task).all()
        return {'tasks': [t.serialize() for t in tasks]}
```

- `caching_class`: A subclass of `BaseCache` (default: `None`).
- `caching_method_names`: List of method names to cache (e.g., `['get', 'post']`).

## Cache Key Generation and Timeout

The `RedisCache` uses an MD5 hash of the cache key string. You can override timeouts by passing `timeout` to `set`:

```python
cache = RedisCache()
cache.set('custom-key', {'foo': 'bar'}, timeout=600)
```

## Direct Cache Access

If you need to interact with the cache directly in your endpoint, use `self.cache`:

```python
def post(self, request):
    data = request.data
    created = create_item(data)
    # Invalidate cache manually
    self.cache.set('tasks', [])  # or delete with a custom method
    return {'created': created}, 201
```
