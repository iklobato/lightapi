# Authentication API Reference

The Authentication module provides secure authentication capabilities for LightAPI applications with built-in JWT support and CORS compatibility.

## BaseAuthentication

::: lightapi.auth.BaseAuthentication

Base class for all authentication implementations. Provides a common interface for authentication methods.

### Basic Usage

```python
from lightapi.auth import BaseAuthentication
from starlette.responses import JSONResponse

class CustomAuth(BaseAuthentication):
    def authenticate(self, request):
        # Return True if authenticated, False otherwise
        api_key = request.headers.get('X-API-Key')
        if api_key == 'valid-key':
            request.state.user = {'api_key': api_key}
            return True
        return False
    
    def get_auth_error_response(self, request):
        return JSONResponse(
            {"error": "Invalid API key"}, 
            status_code=403
        )
```

### Methods

#### authenticate(request)

Authenticate an HTTP request.

**Parameters:**
- `request`: HTTP request object

**Returns:**
- `bool`: True if authentication succeeds, False otherwise

**Default Behavior:**
- Returns `True` (allows all requests)
- Override this method to implement custom authentication logic

#### get_auth_error_response(request)

Generate error response for failed authentication.

**Parameters:**
- `request`: HTTP request object

**Returns:**
- `Response`: HTTP response for authentication failure

**Default Response:**
```json
{
    "error": "not allowed"
}
```
*Status Code: 403*

---

## JWTAuthentication

::: lightapi.auth.JWTAuthentication

JWT (JSON Web Token) based authentication with automatic CORS support.

### Configuration

JWT authentication requires a secret key for token signing:

```bash
# Environment variable (recommended)
export LIGHTAPI_JWT_SECRET="your-super-secret-key"
```

```python
from lightapi.config import config

# Programmatic configuration
config.jwt_secret = "your-secret-key"
```

### Basic Usage

```python
from lightapi.auth import JWTAuthentication

class ProtectedEndpoint(RestEndpoint):
    __tablename__ = 'protected_data'
    
    id = Column(Integer, primary_key=True)
    data = Column(String(255))
    
    class Configuration:
        authentication_class = JWTAuthentication
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| No parameters | - | - | Uses config.jwt_secret for token signing |

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `secret_key` | `str` | Secret key for signing tokens |
| `algorithm` | `str` | JWT algorithm (default: "HS256") |
| `expiration` | `int` | Default token expiration in seconds (default: 3600) |

### Methods

#### generate_token(payload, expiration=None)

Generate a JWT token with the given payload.

```python
auth = JWTAuthentication()
token = auth.generate_token({
    'sub': 'user_123',
    'username': 'john_doe',
    'role': 'admin'
}, expiration=7200)  # 2 hours
```

**Parameters:**
- `payload` (Dict): Data to encode in the token
- `expiration` (Optional[int]): Token expiration in seconds

**Returns:**
- `str`: Encoded JWT token

**Example Token Payload:**
```json
{
    "sub": "user_123",
    "username": "john_doe", 
    "role": "admin",
    "exp": 1640995200
}
```

#### decode_token(token)

Decode and verify a JWT token.

```python
auth = JWTAuthentication()
try:
    payload = auth.decode_token(token)
    user_id = payload['sub']
    role = payload['role']
except jwt.InvalidTokenError:
    # Handle invalid token
    pass
```

**Parameters:**
- `token` (str): JWT token to decode

**Returns:**
- `Dict`: Decoded token payload

**Raises:**
- `jwt.InvalidTokenError`: If token is invalid or expired

#### authenticate(request)

Authenticate a request using JWT token from Authorization header.

**Request Headers:**
```
Authorization: Bearer <jwt_token>
```

**Behavior:**
- Automatically allows OPTIONS requests (CORS preflight)
- Extracts token from "Bearer" format
- Validates token signature and expiration
- Stores decoded payload in `request.state.user`

**Returns:**
- `True`: If authentication succeeds or is OPTIONS request
- `False`: If token is missing, invalid, or expired

### CORS Support

JWT authentication automatically handles CORS preflight requests:

```python
# OPTIONS requests are automatically allowed
# No authentication required for CORS preflight
if request.method == 'OPTIONS':
    return True
```

### Error Responses

Authentication failures return consistent error responses:

```python
# Missing or invalid token
{
    "error": "not allowed"
}
# Status: 403 Forbidden
```

---

## Advanced Authentication Patterns

### Custom JWT Configuration

```python
class CustomJWTAuth(JWTAuthentication):
    def __init__(self):
        super().__init__()
        self.algorithm = "HS512"
        self.expiration = 7200  # 2 hours
    
    def get_auth_error_response(self, request):
        return JSONResponse({
            "error": "Authentication required",
            "code": "AUTH_REQUIRED",
            "timestamp": time.time()
        }, status_code=401)
```

### API Key Authentication

```python
class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return False
        
        # Validate against database or config
        valid_keys = ['key1', 'key2', 'key3']
        if api_key in valid_keys:
            request.state.user = {
                'api_key': api_key,
                'authenticated_via': 'api_key'
            }
            return True
        
        return False
    
    def get_auth_error_response(self, request):
        return JSONResponse({
            "error": "Invalid API key",
            "required_header": "X-API-Key"
        }, status_code=401)
```

### Multi-Factor Authentication

```python
class MFAAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # First, validate JWT token
        if not super().authenticate(request):
            return False
        
        # Then check MFA token
        mfa_token = request.headers.get('X-MFA-Token')
        if not mfa_token:
            return False
        
        # Validate MFA token (implement your MFA logic)
        if self.validate_mfa_token(request.state.user.get('sub'), mfa_token):
            return True
        
        return False
    
    def validate_mfa_token(self, user_id, mfa_token):
        # Implement TOTP, SMS, or other MFA validation
        return True  # Placeholder
```

### Database-Based Authentication

```python
class DatabaseAuth(BaseAuthentication):
    def __init__(self, session_factory):
        self.Session = session_factory
    
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return False
        
        token = auth_header.split(' ')[1]
        session = self.Session()
        
        try:
            # Look up token in database
            auth_token = session.query(AuthToken).filter_by(
                token=token,
                is_active=True
            ).first()
            
            if auth_token and auth_token.expires_at > datetime.utcnow():
                request.state.user = {
                    'user_id': auth_token.user_id,
                    'token_id': auth_token.id
                }
                return True
            
            return False
        finally:
            session.close()
```

---

## Authentication Middleware

### Global Authentication

Apply authentication to all endpoints:

```python
from lightapi.core import AuthenticationMiddleware

app = LightApi()
app.add_middleware([
    AuthenticationMiddleware(JWTAuthentication())
])
```

### Selective Authentication

Apply authentication only to specific endpoints:

```python
# Public endpoint (no authentication)
class PublicEndpoint(RestEndpoint):
    __abstract__ = True
    
    def get(self, request):
        return {"message": "Public data"}, 200

# Protected endpoint
class ProtectedEndpoint(RestEndpoint):
    __abstract__ = True
    
    class Configuration:
        authentication_class = JWTAuthentication
    
    def get(self, request):
        user = request.state.user
        return {"message": f"Hello {user['username']}"}, 200
```

---

## Security Best Practices

### 1. Secret Key Management

```python
# ❌ Bad - hardcoded secret
jwt_secret = "my-secret-key"

# ✅ Good - environment variable
import os
jwt_secret = os.getenv('LIGHTAPI_JWT_SECRET')

# ✅ Better - generated secret
import secrets
jwt_secret = secrets.token_urlsafe(32)

# ✅ Best - external secret management
# Use AWS Secrets Manager, HashiCorp Vault, etc.
```

### 2. Token Expiration

```python
class SecureJWTAuth(JWTAuthentication):
    def generate_token(self, payload, expiration=None):
        # Short-lived tokens for security
        exp = expiration or 900  # 15 minutes
        return super().generate_token(payload, exp)
```

### 3. Token Refresh Pattern

```python
class RefreshableJWTAuth(JWTAuthentication):
    def generate_tokens(self, payload):
        """Generate both access and refresh tokens"""
        access_token = self.generate_token(payload, expiration=900)  # 15 min
        refresh_token = self.generate_token({
            **payload, 
            'type': 'refresh'
        }, expiration=86400)  # 24 hours
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': 900
        }
```

### 4. Rate Limiting

```python
class RateLimitedAuth(JWTAuthentication):
    def __init__(self):
        super().__init__()
        self.failed_attempts = {}
    
    def authenticate(self, request):
        client_ip = request.client.host
        
        # Check rate limit
        if self.is_rate_limited(client_ip):
            return False
        
        success = super().authenticate(request)
        
        if not success:
            self.record_failed_attempt(client_ip)
        else:
            self.clear_failed_attempts(client_ip)
        
        return success
    
    def is_rate_limited(self, ip):
        attempts = self.failed_attempts.get(ip, 0)
        return attempts >= 5  # Max 5 failed attempts
```

---

## Testing Authentication

### Unit Tests

```python
import pytest
from lightapi.auth import JWTAuthentication

def test_jwt_token_generation():
    auth = JWTAuthentication()
    payload = {'user_id': 123, 'role': 'admin'}
    
    token = auth.generate_token(payload)
    assert token is not None
    
    decoded = auth.decode_token(token)
    assert decoded['user_id'] == 123
    assert decoded['role'] == 'admin'

def test_jwt_authentication_with_valid_token():
    # Mock request with valid token
    class MockRequest:
        def __init__(self, token):
            self.headers = {'Authorization': f'Bearer {token}'}
            self.method = 'GET'
            self.state = type('State', (), {})()
    
    auth = JWTAuthentication()
    token = auth.generate_token({'user_id': 123})
    request = MockRequest(token)
    
    assert auth.authenticate(request) == True
    assert request.state.user['user_id'] == 123

def test_jwt_authentication_with_invalid_token():
    class MockRequest:
        def __init__(self):
            self.headers = {'Authorization': 'Bearer invalid.token.here'}
            self.method = 'GET'
            self.state = type('State', (), {})()
    
    auth = JWTAuthentication()
    request = MockRequest()
    
    assert auth.authenticate(request) == False
```

### Integration Tests

```python
def test_protected_endpoint_without_auth(client):
    response = client.get('/protected')
    assert response.status_code == 403
    assert 'error' in response.json()

def test_protected_endpoint_with_auth(client, auth_token):
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = client.get('/protected', headers=headers)
    assert response.status_code == 200

def test_cors_preflight_request(client):
    # OPTIONS requests should work without authentication
    response = client.options('/protected')
    assert response.status_code == 200
```

---

## Troubleshooting

### Common Issues

1. **"JWT secret key not configured"**
   ```bash
   export LIGHTAPI_JWT_SECRET="your-secret-key"
   ```

2. **Token validation fails**
   ```python
   # Debug token validation
   try:
       payload = auth.decode_token(token)
       print(f"Token valid: {payload}")
   except jwt.ExpiredSignatureError:
       print("Token expired")
   except jwt.InvalidTokenError as e:
       print(f"Invalid token: {e}")
   ```

3. **CORS issues with authentication**
   ```python
   # Ensure OPTIONS is in allowed methods
   class ProtectedEndpoint(RestEndpoint):
       class Configuration:
           authentication_class = JWTAuthentication
           http_method_names = ['GET', 'POST', 'OPTIONS']
   ```

### Debug Authentication

```python
class DebugAuth(JWTAuthentication):
    def authenticate(self, request):
        print(f"Method: {request.method}")
        print(f"Headers: {dict(request.headers)}")
        
        result = super().authenticate(request)
        print(f"Auth result: {result}")
        
        if hasattr(request.state, 'user'):
            print(f"User: {request.state.user}")
        
        return result
```

## See Also

- **[Core API](core.md)** - Application and middleware setup
- **[REST Endpoints](rest.md)** - Endpoint authentication configuration
- **[Authentication Example](../examples/auth.md)** - Complete implementation example 