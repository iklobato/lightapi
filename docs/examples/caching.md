# Caching Example

This example demonstrates how to implement Redis-based caching in LightAPI for improved performance.

## Overview

The caching example shows how to:
- Set up Redis caching for endpoints
- Cache GET responses automatically
- Create custom cache keys
- Handle cache invalidation
- Implement cache warming strategies

## Complete Code

```python
--8<-- "examples/caching_example.py"
```

## Key Components

### 1. Redis Setup

```python
from lightapi.cache import RedisCache

# Basic Redis configuration
cache = RedisCache(host="localhost", port=6379, db=0)

# Production configuration
cache = RedisCache(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=int(os.getenv('REDIS_DB', 0))
)
```

**Environment Setup:**
```bash
# Development
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0

# Production (Redis Cloud example)
export REDIS_HOST=redis-12345.c123.region.cloud.redislabs.com
export REDIS_PORT=12345
export REDIS_PASSWORD=your-redis-password
```

### 2. Basic Cached Endpoint

```python
@register_model_class
class CachedProduct(RestEndpoint):
    __tablename__ = 'cached_products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    price = Column(Float)
    category = Column(String(100))
    description = Column(Text)
    
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']  # Only cache GET requests
```

**Features:**
- Automatic caching of GET responses
- Cache key based on URL and query parameters
- Default 300-second (5-minute) cache timeout
- Transparent cache hits/misses

### 3. Custom Cache Configuration

```python
class CustomCachedProduct(RestEndpoint):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    price = Column(Float)
    
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']
    
    def get(self, request):
        # Custom cache timeout for this endpoint
        cache_key = self._generate_cache_key(request)
        
        # Try to get from cache first
        if hasattr(self, 'cache'):
            cached_result = self.cache.get(cache_key)
            if cached_result:
                return cached_result['data'], cached_result['status_code']
        
        # If not cached, get from database
        query = self.session.query(self.__class__)
        
        # Apply filters
        category = request.query_params.get('category')
        if category:
            query = query.filter_by(category=category)
            
        results = query.all()
        response_data = [product.as_dict() for product in results]
        
        # Cache the result with custom timeout (1 hour)
        if hasattr(self, 'cache'):
            self.cache.set(cache_key, {
                'data': response_data,
                'status_code': 200
            }, timeout=3600)
        
        return response_data, 200
    
    def _generate_cache_key(self, request):
        # Create custom cache key
        base_key = f"{self.__class__.__name__}:{request.url.path}"
        if request.query_params:
            query_string = "&".join(f"{k}={v}" for k, v in request.query_params.items())
            base_key += f"?{query_string}"
        return base_key
```

### 4. Cache Invalidation

```python
class SmartCachedProduct(RestEndpoint):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    price = Column(Float)
    
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']
    
    def post(self, request):
        # Create new product
        result = super().post(request)
        
        # Invalidate relevant caches
        self._invalidate_product_caches()
        
        return result
    
    def put(self, request):
        # Update product
        result = super().put(request)
        
        # Invalidate relevant caches
        self._invalidate_product_caches()
        
        return result
    
    def delete(self, request):
        # Delete product
        result = super().delete(request)
        
        # Invalidate relevant caches
        self._invalidate_product_caches()
        
        return result
    
    def _invalidate_product_caches(self):
        """Invalidate all product-related caches"""
        if hasattr(self, 'cache'):
            # Invalidate main product list cache
            cache_patterns = [
                f"{self.__class__.__name__}:/products",
                f"{self.__class__.__name__}:/products?*"
            ]
            
            for pattern in cache_patterns:
                # Note: This is a simplified example
                # Redis supports pattern-based deletion with SCAN
                try:
                    self.cache.client.delete(pattern)
                except:
                    pass  # Continue if cache deletion fails
```

### 5. Advanced Caching Patterns

```python
class AdvancedCachedEndpoint(RestEndpoint):
    __tablename__ = 'advanced_items'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    category_id = Column(Integer)
    
    class Configuration:
        caching_class = RedisCache
    
    def get(self, request):
        """GET with hierarchical caching"""
        # Check for specific item request
        item_id = request.query_params.get('id')
        if item_id:
            return self._get_cached_item(item_id)
        
        # Check for category-based request
        category_id = request.query_params.get('category_id')
        if category_id:
            return self._get_cached_category_items(category_id)
        
        # Default: get all items
        return self._get_cached_all_items()
    
    def _get_cached_item(self, item_id):
        """Cache individual items"""
        cache_key = f"item:{item_id}"
        
        # Try cache first
        cached_item = self.cache.get(cache_key)
        if cached_item:
            return cached_item, 200
        
        # Get from database
        item = self.session.query(self.__class__).filter_by(id=item_id).first()
        if not item:
            return {"error": "Item not found"}, 404
        
        item_data = item.as_dict()
        
        # Cache individual item (long timeout - items don't change often)
        self.cache.set(cache_key, item_data, timeout=7200)  # 2 hours
        
        return item_data, 200
    
    def _get_cached_category_items(self, category_id):
        """Cache items by category"""
        cache_key = f"category:{category_id}:items"
        
        # Try cache first
        cached_items = self.cache.get(cache_key)
        if cached_items:
            return cached_items, 200
        
        # Get from database
        items = self.session.query(self.__class__).filter_by(category_id=category_id).all()
        items_data = [item.as_dict() for item in items]
        
        # Cache category items (medium timeout)
        self.cache.set(cache_key, items_data, timeout=1800)  # 30 minutes
        
        return items_data, 200
    
    def _get_cached_all_items(self):
        """Cache all items"""
        cache_key = "all_items"
        
        # Try cache first
        cached_items = self.cache.get(cache_key)
        if cached_items:
            return cached_items, 200
        
        # Get from database
        items = self.session.query(self.__class__).all()
        items_data = [item.as_dict() for item in items]
        
        # Cache all items (short timeout - changes frequently)
        self.cache.set(cache_key, items_data, timeout=600)  # 10 minutes
        
        return items_data, 200
```

## Usage Examples

### 1. Basic Cached Requests

```bash
# First request (cache miss)
curl http://localhost:8000/products
# Response time: ~200ms

# Second request (cache hit)
curl http://localhost:8000/products
# Response time: ~5ms
```

### 2. Cache with Query Parameters

```bash
# Different cache entries for different queries
curl http://localhost:8000/products
curl http://localhost:8000/products?category=electronics
curl http://localhost:8000/products?category=books
```

### 3. Cache Headers

```bash
# Check cache status in response headers
curl -v http://localhost:8000/products

# Response headers might include:
# X-Cache-Status: HIT
# X-Cache-Key: CachedProduct:/products
# X-Cache-TTL: 245
```

## Performance Benefits

### Before Caching

```python
# Typical database query times
# Simple query: 50-100ms
# Complex query with joins: 200-500ms
# High traffic: Database overload, slow responses
```

### After Caching

```python
# Cache hit times
# Redis local: 1-5ms
# Redis remote: 5-15ms
# Memory cache: <1ms

# Benefits:
# - 90%+ response time improvement
# - Reduced database load
# - Better user experience
# - Higher throughput
```

## Cache Monitoring

### 1. Cache Statistics

```python
class CacheStatsEndpoint(RestEndpoint):
    __abstract__ = True
    
    def get(self, request):
        if hasattr(self, 'cache'):
            # Get Redis stats
            info = self.cache.client.info()
            
            return {
                "redis_info": {
                    "used_memory": info['used_memory'],
                    "connected_clients": info['connected_clients'],
                    "total_commands_processed": info['total_commands_processed'],
                    "keyspace_hits": info['keyspace_hits'],
                    "keyspace_misses": info['keyspace_misses'],
                    "hit_rate": info['keyspace_hits'] / (info['keyspace_hits'] + info['keyspace_misses']) * 100
                }
            }, 200
        
        return {"error": "Cache not configured"}, 500
```

### 2. Cache Health Check

```python
class CacheHealthEndpoint(RestEndpoint):
    __abstract__ = True
    
    def get(self, request):
        try:
            # Test cache connectivity
            cache = RedisCache()
            test_key = "health_check"
            test_value = {"status": "ok", "timestamp": time.time()}
            
            # Write test
            cache.set(test_key, test_value, timeout=60)
            
            # Read test
            result = cache.get(test_key)
            
            if result and result.get("status") == "ok":
                return {
                    "cache_status": "healthy",
                    "latency_ms": (time.time() - result["timestamp"]) * 1000
                }, 200
            else:
                return {"cache_status": "unhealthy", "error": "Read test failed"}, 500
                
        except Exception as e:
            return {"cache_status": "unhealthy", "error": str(e)}, 500
```

## Advanced Patterns

### 1. Cache Warming

```python
class CacheWarmingService:
    def __init__(self, app):
        self.app = app
        self.cache = RedisCache()
    
    def warm_popular_data(self):
        """Pre-populate cache with frequently accessed data"""
        # Warm up popular products
        popular_categories = ['electronics', 'books', 'clothing']
        
        for category in popular_categories:
            # Simulate request to warm cache
            fake_request = self._create_fake_request(f'/products?category={category}')
            endpoint = CachedProduct()
            endpoint.cache = self.cache
            endpoint.get(fake_request)
    
    def _create_fake_request(self, path):
        # Create minimal request object for cache warming
        class FakeRequest:
            def __init__(self, path):
                self.url = type('obj', (object,), {'path': path})
                self.query_params = {}
                if '?' in path:
                    path, query_string = path.split('?', 1)
                    self.query_params = dict(param.split('=') for param in query_string.split('&'))
        
        return FakeRequest(path)
```

### 2. Cache Tags and Invalidation

```python
class TaggedCacheEndpoint(RestEndpoint):
    __tablename__ = 'tagged_items'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    category_id = Column(Integer)
    
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']
    
    def get(self, request):
        # Get data with tags
        result = super().get(request)
        
        # Tag the cache entry
        if hasattr(self, 'cache'):
            cache_key = self._generate_cache_key(request)
            tags = [
                f"table:{self.__tablename__}",
                f"endpoint:{self.__class__.__name__}"
            ]
            
            # Store tags in a separate cache key
            for tag in tags:
                tag_key = f"tag:{tag}"
                tagged_keys = self.cache.get(tag_key) or []
                if cache_key not in tagged_keys:
                    tagged_keys.append(cache_key)
                    self.cache.set(tag_key, tagged_keys, timeout=86400)  # 24 hours
        
        return result
    
    def invalidate_by_tag(self, tag):
        """Invalidate all cache keys with a specific tag"""
        tag_key = f"tag:{tag}"
        tagged_keys = self.cache.get(tag_key) or []
        
        for cache_key in tagged_keys:
            self.cache.client.delete(cache_key)
        
        # Clear the tag itself
        self.cache.client.delete(tag_key)
```

### 3. Distributed Cache Locking

```python
import time
import uuid

class DistributedCacheEndpoint(RestEndpoint):
    __tablename__ = 'expensive_items'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    
    class Configuration:
        caching_class = RedisCache
    
    def get(self, request):
        cache_key = self._generate_cache_key(request)
        lock_key = f"lock:{cache_key}"
        
        # Try to get from cache first
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result['data'], cached_result['status_code']
        
        # Acquire distributed lock to prevent cache stampede
        lock_acquired = self._acquire_lock(lock_key, timeout=30)
        if not lock_acquired:
            # Wait briefly and try cache again
            time.sleep(0.1)
            cached_result = self.cache.get(cache_key)
            if cached_result:
                return cached_result['data'], cached_result['status_code']
        
        try:
            # Expensive operation (simulate complex calculation)
            result = self._expensive_operation(request)
            
            # Cache the result
            self.cache.set(cache_key, {
                'data': result,
                'status_code': 200
            }, timeout=3600)
            
            return result, 200
            
        finally:
            # Always release the lock
            if lock_acquired:
                self._release_lock(lock_key)
    
    def _acquire_lock(self, lock_key, timeout=30):
        """Acquire a distributed lock"""
        lock_id = str(uuid.uuid4())
        end_time = time.time() + timeout
        
        while time.time() < end_time:
            # Try to set lock with expiration
            if self.cache.client.set(lock_key, lock_id, nx=True, ex=timeout):
                self._lock_id = lock_id
                return True
            time.sleep(0.01)  # Brief pause before retry
        
        return False
    
    def _release_lock(self, lock_key):
        """Release a distributed lock"""
        # Only release if we own the lock
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        self.cache.client.eval(lua_script, 1, lock_key, self._lock_id)
    
    def _expensive_operation(self, request):
        """Simulate expensive database/computation operation"""
        time.sleep(2)  # Simulate 2-second operation
        return {"result": "expensive_computation_complete", "timestamp": time.time()}
```

## Configuration Best Practices

### 1. Environment-Based Configuration

```python
import os

class ProductionCacheConfig:
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
    
    # Cache timeouts by data type
    CACHE_TIMEOUTS = {
        'static_data': 3600 * 24,      # 24 hours
        'user_data': 3600,             # 1 hour
        'search_results': 300,         # 5 minutes
        'real_time_data': 60,          # 1 minute
    }

# Use in endpoint
class ConfiguredCachedEndpoint(RestEndpoint):
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']
    
    def get(self, request):
        cache_timeout = ProductionCacheConfig.CACHE_TIMEOUTS['user_data']
        # Use timeout in caching logic
```

### 2. Cache Key Strategies

```python
def generate_smart_cache_key(self, request, user_specific=False):
    """Generate cache keys with different strategies"""
    key_parts = [
        self.__class__.__name__,
        request.url.path
    ]
    
    # Add user-specific component
    if user_specific and hasattr(request, 'state') and hasattr(request.state, 'user'):
        key_parts.append(f"user:{request.state.user.get('sub')}")
    
    # Add query parameters (sorted for consistency)
    if request.query_params:
        sorted_params = sorted(request.query_params.items())
        query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
        key_parts.append(query_string)
    
    return ":".join(key_parts)
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```python
   # Check Redis connectivity
   import redis
   try:
       r = redis.Redis(host='localhost', port=6379, db=0)
       r.ping()
       print("Redis connected successfully")
   except redis.ConnectionError:
       print("Failed to connect to Redis")
   ```

2. **Cache Not Working**
   ```python
   # Debug cache configuration
   def debug_cache(self, request):
       print(f"Cache class: {getattr(self, 'cache', 'Not configured')}")
       print(f"Cache methods: {getattr(self.Configuration, 'caching_method_names', [])}")
       print(f"Current method: {request.method}")
   ```

3. **Memory Issues**
   ```bash
   # Monitor Redis memory usage
   redis-cli info memory
   
   # Set memory limits in redis.conf
   maxmemory 2gb
   maxmemory-policy allkeys-lru
   ```

### Performance Optimization

```python
# Use Redis pipelines for bulk operations
def bulk_cache_operations(self, cache_data):
    pipe = self.cache.client.pipeline()
    
    for key, value in cache_data.items():
        pipe.set(key, json.dumps(value), ex=3600)
    
    pipe.execute()  # Execute all operations at once
```

## Next Steps

- **[Filtering and Pagination](filtering-pagination.md)** - Query optimization
- **[Middleware Example](middleware.md)** - Custom middleware patterns
- **[API Reference](../api-reference/cache.md)** - Caching API details
- **[Performance Guide](../advanced/performance.md)** - Advanced optimization 