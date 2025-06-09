# Core API Reference

The Core API module provides the fundamental building blocks of LightAPI. It contains the base classes and utilities that power the framework's core functionality.

## Core Components

### LightApi Class

The main class that initializes and configures the framework.

```python
from lightapi.core import LightApi

app = LightApi(database_url="sqlite:///app.db")
```

#### Configuration Options

- `database_url` (str): Database connection URL
- `swagger_title` (str): API documentation title
- `swagger_version` (str): API version
- `swagger_description` (str): API description

### Built-in Middleware Classes

#### CORSMiddleware

Handles Cross-Origin Resource Sharing (CORS) automatically:

```python
from lightapi.core import CORSMiddleware

# Basic CORS
cors_middleware = CORSMiddleware()

# Custom CORS configuration
cors_middleware = CORSMiddleware(
    allow_origins=['https://myapp.com'],
    allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type'],
    allow_credentials=True
)

app.add_middleware([cors_middleware])
```

**Parameters:**
- `allow_origins` (list): Allowed origin domains
- `allow_methods` (list): Allowed HTTP methods
- `allow_headers` (list): Allowed request headers
- `allow_credentials` (bool): Allow credentials

#### AuthenticationMiddleware

Applies authentication globally to all endpoints:

```python
from lightapi.core import AuthenticationMiddleware
from lightapi.auth import JWTAuthentication

# Apply JWT authentication to all endpoints
auth_middleware = AuthenticationMiddleware(JWTAuthentication)
app.add_middleware([auth_middleware])
```

**Parameters:**
- `authentication_class` (class): Authentication class to use

#### Base Middleware Class

Create custom middleware by subclassing:

```python
from lightapi.core import Middleware

class CustomMiddleware(Middleware):
    def process(self, request, response):
        # Pre-processing (response is None)
        if response is None:
            # Handle before endpoint
            return None
        
        # Post-processing
        # Handle after endpoint
        return response
```

### Response Classes

#### Response

Custom response class for additional control:

```python
from lightapi.core import Response

# Basic response
response = Response({"data": "value"}, status_code=200)

# Response with headers
response = Response(
    {"data": "value"}, 
    status_code=200,
    headers={"X-Custom": "header"}
)
```

**Parameters:**
- `body` (any): Response body content
- `status_code` (int): HTTP status code
- `headers` (dict): Response headers
- `content_type` (str): Content type

### Request Handling

The core module provides robust request handling:

```python
from lightapi.rest import RestEndpoint

class UserEndpoint(RestEndpoint):
    def get(self, request):
        # Access request data
        user_id = request.path_params.get('id')
        query_params = request.query_params
        user_info = request.state.user  # From authentication
        
        return {'user_id': user_id}
```

### Application Setup

```python
from lightapi.core import LightApi

# Initialize with database
app = LightApi(database_url="postgresql://user:pass@localhost/db")

# Register endpoints
app.register({
    '/users': UserEndpoint,
    '/products': ProductEndpoint
})

# Add middleware
app.add_middleware([
    CORSMiddleware(),
    AuthenticationMiddleware(JWTAuthentication)
])

# Run application
app.run(host="0.0.0.0", port=8000, debug=True, reload=True)
```

## Core Utilities

### Environment Configuration

LightAPI supports configuration via environment variables:

```python
import os

# Server configuration
os.environ['LIGHTAPI_HOST'] = '0.0.0.0'
os.environ['LIGHTAPI_PORT'] = '8000'
os.environ['LIGHTAPI_DEBUG'] = 'True'

# Database
os.environ['LIGHTAPI_DATABASE_URL'] = 'postgresql://user:pass@localhost/db'

# JWT Authentication
os.environ['LIGHTAPI_JWT_SECRET'] = 'your-secret-key'

# Redis Caching
os.environ['LIGHTAPI_REDIS_HOST'] = 'localhost'
os.environ['LIGHTAPI_REDIS_PORT'] = '6379'
```

### Middleware Registration

Middleware can be registered in order of execution:

```python
# Middleware executes in registration order
app.add_middleware([
    LoggingMiddleware,        # First
    CORSMiddleware(),         # Second
    AuthenticationMiddleware(JWTAuthentication),  # Third
    TimingMiddleware         # Last
])
```

## Best Practices

1. **Initialize LightApi with proper database URL** for production environments
2. **Register CORS middleware** when building APIs for web applications
3. **Use environment variables** for configuration instead of hardcoding values
4. **Register middleware in logical order** (logging → CORS → auth → custom)
5. **Use built-in middleware** instead of implementing custom solutions for common needs
6. **Enable debug and reload** during development, disable in production

## Complete Example

Here's a complete example using all core features:

```python
import os
from lightapi.core import LightApi, CORSMiddleware, AuthenticationMiddleware
from lightapi.auth import JWTAuthentication
from lightapi.rest import RestEndpoint

# Environment configuration
os.environ['LIGHTAPI_JWT_SECRET'] = 'your-secret-key'

class UserEndpoint(RestEndpoint):
    __tablename__ = 'users'
    
    class Configuration:
        http_method_names = ['GET', 'POST', 'OPTIONS']

    def get(self, request):
        # Authentication handled automatically
        user = request.state.user
        return {'message': f'Hello {user["user_id"]}'}

# Initialize app
app = LightApi(database_url="sqlite:///app.db")

# Register endpoints
app.register({'/users': UserEndpoint})

# Add middleware
app.add_middleware([
    CORSMiddleware(
        allow_origins=['https://myapp.com'],
        allow_methods=['GET', 'POST', 'OPTIONS']
    ),
    AuthenticationMiddleware(JWTAuthentication)
])

if __name__ == '__main__':
    app.run(debug=True, reload=True)
```

## See Also

- [Authentication](auth.md) - Authentication classes
- [Middleware](../advanced/middleware.md) - Custom middleware implementation
- [REST Endpoints](rest.md) - RestEndpoint class 