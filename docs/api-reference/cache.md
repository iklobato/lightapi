# Caching Reference

The Caching module provides Redis-based caching capabilities for improved performance in LightAPI applications.

## Cache Configuration

### Basic Setup

```python
from lightapi.cache import Cache

cache = Cache('redis://localhost:6379/0')
```

### Advanced Configuration

```python
cache = Cache(
    'redis://localhost:6379/0',
    prefix='myapp:',
    default_timeout=3600,
    serializer='json'
)
```

## Basic Operations

### Setting Values

```python
# Basic set
cache.set('key', 'value')

# Set with timeout
cache.set('key', 'value', timeout=300)  # 5 minutes

# Set multiple values
cache.set_many({
    'key1': 'value1',
    'key2': 'value2'
})
```

### Getting Values

```python
# Get single value
value = cache.get('key')

# Get with default
value = cache.get('key', default='default_value')

# Get multiple values
values = cache.get_many(['key1', 'key2'])
```

### Deleting Values

```python
# Delete single key
cache.delete('key')

# Delete multiple keys
cache.delete_many(['key1', 'key2'])

# Clear all keys
cache.clear()
```

## Decorators

### Function Caching

```python
from lightapi.cache import cached

@cached(timeout=300)
def expensive_operation():
    # ... perform expensive operation ...
    return result
```

### Method Caching

```python
class UserService:
    @cached(timeout=300)
    def get_user_data(self, user_id):
        # ... fetch user data ...
        return data
```

## Advanced Features

### Pattern-based Operations

```python
# Delete all keys matching pattern
cache.delete_pattern('user:*')

# Get all keys matching pattern
keys = cache.keys('user:*')
```

### Cache Tags

```python
# Set with tags
cache.set('user:1', data, tags=['users'])

# Invalidate by tag
cache.invalidate_tags(['users'])
```

## Examples

### Complete Caching Setup

```python
from lightapi import LightAPI
from lightapi.cache import Cache, cached

# Initialize app and cache
app = LightAPI()
cache = Cache('redis://localhost:6379/0')

# Cache endpoint response
@app.route('/users')
@cached(timeout=300)
def get_users():
    users = User.query.all()
    return {'users': [user.to_dict() for user in users]}

# Cache with dynamic key
@app.route('/user/<id>')
@cached(key_prefix='user:{id}')
def get_user(id):
    user = User.query.get(id)
    return user.to_dict()

# Manual cache management
@app.route('/update-user/<id>', methods=['POST'])
def update_user(id):
    user = User.query.get(id)
    user.update(request.json)
    db.session.commit()
    
    # Invalidate cache
    cache.delete(f'user:{id}')
    cache.invalidate_tags(['users'])
    
    return {'message': 'User updated'}
```

## Best Practices

1. Use appropriate timeout values
2. Implement cache invalidation strategy
3. Use cache tags for related data
4. Monitor cache memory usage
5. Handle cache failures gracefully

## See Also

- [Core API](core.md) - Core framework functionality
- [REST API](rest.md) - REST endpoint implementation
- [Database](database.md) - Database integration 