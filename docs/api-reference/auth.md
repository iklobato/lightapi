# Authentication Reference

The Authentication module provides tools for implementing secure authentication in LightAPI applications with automatic CORS support.

## Base Authentication Classes

### BaseAuthentication

Base class for all authentication implementations:

```python
from lightapi.auth import BaseAuthentication
from starlette.responses import JSONResponse

class CustomAuth(BaseAuthentication):
    def authenticate(self, request):
        # Return True if authenticated, False otherwise
        # Automatically skips OPTIONS requests for CORS
        if request.method == 'OPTIONS':
            return True
        
        # Custom authentication logic
        api_key = request.headers.get('X-API-Key')
        if api_key == 'valid-key':
            request.state.user = {'api_key': api_key}
            return True
        return False
    
    def get_auth_error_response(self, request):
        # Return custom error response
        return JSONResponse(
            {"error": "Invalid API key"}, 
            status_code=403
        )
```

## Built-in Authentication

### JWTAuthentication

JWT-based authentication with automatic CORS preflight support:

```python
from lightapi.auth import JWTAuthentication
import os

# Configure JWT secret
os.environ['LIGHTAPI_JWT_SECRET'] = 'your-secret-key'

# Use in endpoint configuration
class ProtectedEndpoint(RestEndpoint):
    class Configuration:
        authentication_class = JWTAuthentication
        http_method_names = ['GET', 'POST', 'OPTIONS']
```

**Features:**
- Automatic OPTIONS request handling for CORS preflight
- Environment variable configuration
- Consistent error responses
- User information stored in `request.state.user`

**Methods:**

#### `generate_token(payload, expiration=3600)`
Generate a JWT token with the given payload:

```python
auth = JWTAuthentication()
token = auth.generate_token({
    'user_id': 1,
    'role': 'admin'
})
```

#### `authenticate(request)`
Authenticate a request:

```python
# Called automatically by the framework
# Returns True if authenticated, False otherwise
# Automatically allows OPTIONS requests
```

#### `get_auth_error_response(request)`
Get error response for failed authentication:

```python
# Returns JSONResponse with {"error": "not allowed"} and 403 status
```

### Custom JWT Authentication

Override default JWT settings:

```python
from lightapi.auth import JWTAuthentication

class CustomJWT(JWTAuthentication):
    secret_key = 'my-custom-secret'
    algorithm = 'HS512'
    expiration = 7200  # 2 hours
    
    def get_auth_error_response(self, request):
        return JSONResponse(
            {"error": "Authentication required", "code": "AUTH_REQUIRED"}, 
            status_code=401
        )
```

## Authentication Usage

### Endpoint-Level Authentication

Apply authentication to specific endpoints:

```python
from lightapi.rest import RestEndpoint
from lightapi.auth import JWTAuthentication

class UserEndpoint(RestEndpoint):
    class Configuration:
        authentication_class = JWTAuthentication
        http_method_names = ['GET', 'POST', 'OPTIONS']

    def get(self, request):
        # Authentication automatically handled
        # OPTIONS requests bypass authentication
        user = request.state.user
        return {'message': f'Hello {user["user_id"]}'}
```

### Global Authentication Middleware

Apply authentication to all endpoints:

```python
from lightapi.core import LightApi, AuthenticationMiddleware
from lightapi.auth import JWTAuthentication

app = LightApi()

# Apply to all endpoints
app.add_middleware([
    AuthenticationMiddleware(JWTAuthentication)
])

app.register({'/users': UserEndpoint})
```

### Token Generation and Usage

```python
import os
from lightapi.auth import JWTAuthentication

# Set secret via environment variable
os.environ['LIGHTAPI_JWT_SECRET'] = 'your-secret-key'

# Generate token
auth = JWTAuthentication()
token = auth.generate_token({
    'user_id': 123,
    'email': 'user@example.com',
    'role': 'admin'
})

# Use token in requests:
# Authorization: Bearer {token}
```

### CORS Integration

JWT Authentication automatically works with CORS:

```python
from lightapi.core import LightApi, CORSMiddleware
from lightapi.auth import JWTAuthentication

class APIEndpoint(RestEndpoint):
    class Configuration:
        authentication_class = JWTAuthentication
        http_method_names = ['GET', 'POST', 'OPTIONS']

app = LightApi()
app.register({'/api': APIEndpoint})

# Add CORS middleware
app.add_middleware([CORSMiddleware()])

# Request handling:
# OPTIONS /api -> 200 OK (no auth required)
# GET /api -> 403 Forbidden (auth required)
# GET /api with valid token -> 200 OK
```

## Environment Configuration

Configure authentication using environment variables:

```bash
# JWT Authentication
export LIGHTAPI_JWT_SECRET="your-secret-key"
export LIGHTAPI_JWT_ALGORITHM="HS256"
export LIGHTAPI_JWT_EXPIRATION="3600"
```

## Error Responses

Standard authentication error responses:

```json
// Missing or invalid token
{
    "error": "not allowed"
}
// Status: 403 Forbidden
```

## Best Practices

1. **Use environment variables** for secrets and configuration
2. **Include OPTIONS in http_method_names** when using CORS
3. **Use HTTPS** for all authentication endpoints in production
4. **Set appropriate token expiration** times
5. **Use built-in authentication classes** instead of custom implementations
6. **Combine with CORS middleware** for web applications
7. **Store user information** in `request.state.user` for access in endpoints

## Complete Example

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
        user = request.state.user
        return {'message': f'Hello user {user["user_id"]}'}

# Create app
app = LightApi()

# Add middleware (order matters)
app.add_middleware([
    CORSMiddleware(),                        # Handle CORS first
    AuthenticationMiddleware(JWTAuthentication)  # Then authenticate
])

# Register endpoints
app.register({'/users': UserEndpoint})

# Generate token for testing
auth = JWTAuthentication()
token = auth.generate_token({'user_id': 1, 'role': 'user'})
print(f"Test token: {token}")

if __name__ == '__main__':
    app.run(debug=True)
```

## See Also

- [Core API](core.md) - Core framework and middleware
- [REST API](rest.md) - REST endpoint implementation
- [Middleware](../advanced/middleware.md) - Custom middleware development 