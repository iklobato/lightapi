---
title: Caching Implementation
---

LightAPI provides a flexible caching system that can significantly improve API performance by storing and reusing responses. The framework includes built-in Redis support with automatic JSON serialization.

## RedisCache

The `RedisCache` class provides Redis-based caching with automatic serialization:

```python
from lightapi.rest import RestEndpoint
from lightapi.cache import RedisCache

class Product(RestEndpoint):
    __tablename__ = 'products'
    
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']  # Cache GET requests only
        cache_timeout = 3600  # 1 hour cache timeout

    def get(self, request):
        # This response will be cached automatically
        return {'products': [...], 'total': 100}
```

### Automatic JSON Serialization

LightAPI's caching system automatically handles JSON serialization:

- **Python objects** (dicts, lists) are automatically serialized to JSON
- **Cache keys** are generated from request URLs and parameters
- **Cache hits** return the original Python objects, not JSON strings
- **Fixed serialization issues** ensure complex objects cache properly

### Environment Configuration

Configure Redis using environment variables:

```bash
export LIGHTAPI_REDIS_HOST=localhost
export LIGHTAPI_REDIS_PORT=6379
export LIGHTAPI_REDIS_DB=0
export LIGHTAPI_REDIS_PASSWORD=your-password  # Optional
```

Or in your application:

```python
import os
os.environ['LIGHTAPI_REDIS_HOST'] = 'localhost'
os.environ['LIGHTAPI_REDIS_PORT'] = '6379'
```

### Cache Key Generation

Cache keys are automatically generated from:
- Request URL
- Query parameters
- Request method
- Request body (for POST/PUT requests)

```python
# These will have different cache keys:
# GET /products?page=1
# GET /products?page=2
# GET /products?category=electronics
```

### Cache Headers

LightAPI automatically adds cache-related headers:

```python
# Cache hit response includes:
# X-Cache: HIT
# X-Cache-Key: products:/products?page=1

# Cache miss response includes:
# X-Cache: MISS
# X-Cache-Key: products:/products?page=1
```

## Custom Cache Implementation

Create custom cache implementations by subclassing the base cache class:

```python
from lightapi.cache import BaseCache
import json
import time

class MemoryCache(BaseCache):
    def __init__(self):
        self.store = {}
        self.expiry = {}
    
    def get(self, key):
        # Check if key exists and hasn't expired
        if key in self.store:
            if key not in self.expiry or time.time() < self.expiry[key]:
                return json.loads(self.store[key])
            else:
                # Clean up expired key
                del self.store[key]
                if key in self.expiry:
                    del self.expiry[key]
        return None
    
    def set(self, key, value, timeout=3600):
        self.store[key] = json.dumps(value)
        self.expiry[key] = time.time() + timeout
    
    def delete(self, key):
        if key in self.store:
            del self.store[key]
        if key in self.expiry:
            del self.expiry[key]

class Product(RestEndpoint):
    class Configuration:
        caching_class = MemoryCache
        caching_method_names = ['GET']
```

## Cache Invalidation

Caches are automatically invalidated for data-modifying operations:

```python
class Product(RestEndpoint):
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']

    def delete(self, request):
        # This will automatically invalidate the cache
        # for this endpoint after successful deletion
        product_id = request.path_params.get('id')
        # ... delete logic ...
        return {'message': 'Product deleted'}
```

### Manual Cache Invalidation

You can manually invalidate cache entries:

```python
def post(self, request):
    # Create new product
    new_product = self.create_product(request.data)
    
    # Manually invalidate related cache entries
    if hasattr(self, 'cache'):
        # Invalidate list cache
        self.cache.delete('products:/')
        # Invalidate category cache
        category = request.data.get('category')
        if category:
            self.cache.delete(f'products:/?category={category}')
    
    return new_product
```

## Conditional Caching

Cache responses based on conditions:

```python
class Product(RestEndpoint):
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']

    def get(self, request):
        # Don't cache admin requests
        if request.headers.get('X-Admin-User'):
            request.skip_cache = True
        
        # Cache user-specific responses differently
        user_id = getattr(request.state, 'user', {}).get('user_id')
        if user_id:
            # This will create user-specific cache keys
            request.cache_suffix = f'user:{user_id}'
        
        return {'products': [...]}
```

## Cache Statistics

Monitor cache performance:

```python
from lightapi.cache import RedisCache

cache = RedisCache()

# Get cache statistics (if supported by your cache implementation)
stats = cache.get_stats()
print(f"Cache hits: {stats.get('hits', 0)}")
print(f"Cache misses: {stats.get('misses', 0)}")
print(f"Cache keys: {stats.get('keys', 0)}")
```

## Best Practices

### Cache Timeouts
Set appropriate cache timeouts based on data volatility:

```python
class Configuration:
    caching_class = RedisCache
    cache_timeout = {
        'GET': 3600,      # 1 hour for general queries
        'search': 1800,   # 30 minutes for search results
        'details': 7200   # 2 hours for detail views
    }
```

### Cache Warming
Pre-populate cache with frequently accessed data:

```python
def warm_cache(self):
    """Populate cache with popular products"""
    popular_products = self.get_popular_products()
    cache_key = 'products:/popular'
    if hasattr(self, 'cache'):
        self.cache.set(cache_key, popular_products, timeout=3600)
```

### Debugging Cache Issues

Enable cache debugging:

```python
import logging
logging.getLogger('lightapi.cache').setLevel(logging.DEBUG)

# This will log:
# Cache key generation
# Cache hits/misses
# Cache set/delete operations
# Serialization issues
```

## Docker Redis Setup

For development, you can use Docker to run Redis:

```bash
# Start Redis container
docker run -d --name lightapi-redis -p 6379:6379 redis:alpine

# Verify Redis is running
docker ps

# Test Redis connection
redis-cli ping
```

## Production Considerations

### Redis Configuration
For production, configure Redis properly:

```bash
# Redis cluster for high availability
export LIGHTAPI_REDIS_CLUSTER_NODES="redis1:6379,redis2:6379,redis3:6379"

# Redis with authentication
export LIGHTAPI_REDIS_PASSWORD="your-secure-password"

# Redis SSL/TLS
export LIGHTAPI_REDIS_SSL=True
export LIGHTAPI_REDIS_SSL_CERT_REQS="required"
```

### Cache Size Management
Monitor and manage cache size:

```python
class SmartCache(RedisCache):
    def set(self, key, value, timeout=3600):
        # Implement size limits
        if self.get_memory_usage() > self.max_memory:
            self.cleanup_old_entries()
        super().set(key, value, timeout)
```

The caching system is designed to be transparent and efficient, requiring minimal configuration while providing maximum performance benefits.
