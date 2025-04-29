# REST API Reference

The REST API module provides tools and utilities for building RESTful endpoints in LightAPI.

## REST Endpoints

### Basic Endpoint Creation

```python
from lightapi.rest import RESTEndpoint

class UserEndpoint(RESTEndpoint):
    model = User
    route = '/users'
```

### Supported HTTP Methods

- GET
- POST
- PUT
- PATCH
- DELETE

### Response Formatting

```python
class UserEndpoint(RESTEndpoint):
    def format_response(self, data):
        return {
            'status': 'success',
            'data': data
        }
```

## Query Parameters

### Filtering

```python
class UserEndpoint(RESTEndpoint):
    filter_fields = ['name', 'email', 'status']
```

### Pagination

```python
class UserEndpoint(RESTEndpoint):
    paginate = True
    items_per_page = 20
```

## Request Validation

```python
from lightapi.rest import validate_request

class UserEndpoint(RESTEndpoint):
    @validate_request({
        'name': {'type': 'string', 'required': True},
        'email': {'type': 'string', 'format': 'email'}
    })
    def post(self, request):
        # Handle validated request
        pass
```

## Examples

### Complete REST Endpoint

```python
from lightapi.rest import RESTEndpoint
from lightapi.models import User

class UserEndpoint(RESTEndpoint):
    model = User
    route = '/users'
    filter_fields = ['name', 'email', 'status']
    paginate = True
    items_per_page = 20

    @validate_request({
        'name': {'type': 'string', 'required': True},
        'email': {'type': 'string', 'format': 'email'}
    })
    def post(self, request):
        user = self.model.create(**request.json)
        return self.format_response(user)

    def get(self, request):
        users = self.model.query.filter_by(**request.args).all()
        return self.format_response(users)
```

## Best Practices

1. Use RESTEndpoint for CRUD operations
2. Implement proper validation for all inputs
3. Use consistent response formatting
4. Implement proper error handling
5. Use pagination for large datasets

## See Also

- [Core API](core.md) - Core framework functionality
- [Models](models.md) - Data models and schemas
- [Filtering](filters.md) - Advanced filtering options
- [Pagination](pagination.md) - Pagination configuration 