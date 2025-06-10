# Authentication Example

This example demonstrates how to implement JWT (JSON Web Token) authentication in LightAPI.

## Overview

The authentication example shows how to:
- Set up JWT authentication
- Create login endpoints to obtain tokens
- Protect endpoints with authentication
- Access authenticated user information
- Handle authentication errors

## Complete Code

```python
--8<-- "examples/auth_example.py"
```

## Key Components

### 1. JWT Configuration

```python
from lightapi.config import config

# JWT secret key is required for token signing
# Set via environment variable: LIGHTAPI_JWT_SECRET=your-secret-key
```

**Environment Setup:**
```bash
export LIGHTAPI_JWT_SECRET="your-super-secret-key-change-in-production"
```

### 2. Custom Authentication Class

```python
class CustomJWTAuth(JWTAuthentication):
    def __init__(self):
        super().__init__()
        self.secret_key = config.jwt_secret
        
    def authenticate(self, request):
        # Use the parent class implementation
        return super().authenticate(request)
```

**Features:**
- Extends built-in `JWTAuthentication`
- Automatically validates JWT tokens
- Skips authentication for OPTIONS requests (CORS)
- Stores user info in `request.state.user`

### 3. Login Endpoint

```python
class AuthEndpoint(RestEndpoint):
    __abstract__ = True  # Not a database model
    
    def post(self, request):
        data = getattr(request, 'data', {})
        username = data.get('username')
        password = data.get('password')
        
        # Simple authentication (replace with database lookup)
        if username == "admin" and password == "password":
            payload = {
                'sub': 'user_1',
                'username': username,
                'role': 'admin',
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            }
            token = jwt.encode(payload, config.jwt_secret, algorithm="HS256")
            return {"token": token}, 200
        else:
            return Response({"error": "Invalid credentials"}, status_code=401)
```

**Key Points:**
- `__abstract__ = True` means it's not a database model
- Returns JWT token on successful authentication
- Token includes user information and expiration
- Returns 401 for invalid credentials

### 4. Protected Endpoints

```python
class SecretResource(RestEndpoint):
    __abstract__ = True
    
    class Configuration:
        authentication_class = CustomJWTAuth
    
    def get(self, request):
        # Access authenticated user info
        username = request.state.user.get('username')
        role = request.state.user.get('role')
        
        return {
            "message": f"Hello, {username}! You have {role} access.",
            "secret_data": "This is protected information"
        }, 200
```

**Features:**
- Requires valid JWT token
- User info available in `request.state.user`
- Returns 401 if token is missing or invalid

### 5. Database Model with Authentication

```python
@register_model_class
class UserProfile(RestEndpoint):
    __tablename__ = 'user_profiles'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50))
    full_name = Column(String(100))
    email = Column(String(100))
    
    class Configuration:
        authentication_class = CustomJWTAuth
    
    def get(self, request):
        user_id = request.state.user.get('sub')
        profile = self.session.query(self.__class__).filter_by(user_id=user_id).first()
        
        if profile:
            return {
                "id": profile.id,
                "user_id": profile.user_id,
                "full_name": profile.full_name,
                "email": profile.email
            }, 200
        else:
            return Response({"error": "Profile not found"}, status_code=404)
```

## Usage Examples

### 1. Get Authentication Token

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "password"
  }'
```

**Response:**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### 2. Access Public Endpoint

```bash
curl http://localhost:8000/public
```

**Response:**
```json
{
  "message": "This is public information"
}
```

### 3. Access Protected Endpoint

```bash
# Without token (will fail)
curl http://localhost:8000/secret
```

**Response:**
```json
{
  "error": "Authentication failed"
}
```

```bash
# With valid token
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/secret
```

**Response:**
```json
{
  "message": "Hello, admin! You have admin access.",
  "secret_data": "This is protected information"
}
```

### 4. Access User Profile

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/profile
```

## JWT Token Structure

### Token Payload

```json
{
  "sub": "user_1",           // Subject (user ID)
  "username": "admin",       // Username
  "role": "admin",          // User role
  "exp": 1640995200         // Expiration timestamp
}
```

### Token Header

```json
{
  "typ": "JWT",             // Token type
  "alg": "HS256"           // Signing algorithm
}
```

## Security Considerations

### 1. Secret Key Management

```python
# ❌ Bad - hardcoded secret
config.jwt_secret = "my-secret"

# ✅ Good - environment variable
import os
config.jwt_secret = os.getenv('LIGHTAPI_JWT_SECRET')

# ✅ Better - use secrets module for generation
import secrets
secret_key = secrets.token_urlsafe(32)
```

### 2. Token Expiration

```python
def generate_token(self, payload):
    token_data = {
        **payload,
        'exp': datetime.utcnow() + timedelta(hours=1)  # 1 hour expiration
    }
    return jwt.encode(token_data, self.secret_key, algorithm="HS256")
```

### 3. Password Security

```python
import bcrypt

class SecureAuthEndpoint(RestEndpoint):
    def post(self, request):
        data = getattr(request, 'data', {})
        username = data.get('username')
        password = data.get('password')
        
        # Get user from database
        user = self.session.query(User).filter_by(username=username).first()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash):
            token = self.generate_token({'sub': user.id, 'username': username})
            return {"token": token}, 200
        
        return Response({"error": "Invalid credentials"}, status_code=401)
```

## Advanced Authentication Patterns

### 1. Role-Based Access Control

```python
from functools import wraps

def require_role(required_role):
    def decorator(func):
        @wraps(func)
        def wrapper(self, request):
            user_role = request.state.user.get('role')
            if user_role != required_role:
                return Response({"error": "Insufficient permissions"}, status_code=403)
            return func(self, request)
        return wrapper
    return decorator

class AdminEndpoint(RestEndpoint):
    __abstract__ = True
    
    class Configuration:
        authentication_class = CustomJWTAuth
    
    @require_role('admin')
    def get(self, request):
        return {"message": "Admin-only content"}, 200
```

### 2. Custom Authentication Class

```python
class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        api_key = request.headers.get('X-API-Key')
        
        # Validate API key against database
        valid_key = self.session.query(APIKey).filter_by(
            key=api_key, 
            is_active=True
        ).first()
        
        if valid_key:
            request.state.user = {
                'api_key_id': valid_key.id,
                'permissions': valid_key.permissions
            }
            return True
        
        return False

class APIKeyEndpoint(RestEndpoint):
    class Configuration:
        authentication_class = APIKeyAuthentication
```

### 3. Multi-Factor Authentication

```python
class MFAAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # First check JWT token
        if not super().authenticate(request):
            return False
        
        # Then check MFA token
        mfa_token = request.headers.get('X-MFA-Token')
        user_id = request.state.user.get('sub')
        
        # Validate MFA token
        if not self.validate_mfa_token(user_id, mfa_token):
            return False
        
        return True
    
    def validate_mfa_token(self, user_id, token):
        # Implement TOTP or similar MFA validation
        pass
```

## Testing Authentication

### 1. Unit Tests

```python
import pytest
from lightapi.auth import JWTAuthentication

def test_jwt_authentication():
    auth = JWTAuthentication()
    
    # Test token generation
    payload = {'sub': 'user_1', 'username': 'test'}
    token = auth.generate_token(payload)
    assert token is not None
    
    # Test token decoding
    decoded = auth.decode_token(token)
    assert decoded['sub'] == 'user_1'
    assert decoded['username'] == 'test'

def test_invalid_token():
    auth = JWTAuthentication()
    
    with pytest.raises(jwt.InvalidTokenError):
        auth.decode_token('invalid.token.here')
```

### 2. Integration Tests

```python
def test_protected_endpoint(client):
    # Test without token
    response = client.get('/secret')
    assert response.status_code == 401
    
    # Get token
    auth_response = client.post('/auth/login', json={
        'username': 'admin',
        'password': 'password'
    })
    token = auth_response.json()['token']
    
    # Test with token
    response = client.get('/secret', headers={
        'Authorization': f'Bearer {token}'
    })
    assert response.status_code == 200
    assert 'secret_data' in response.json()
```

## Environment Configuration

### Development

```bash
# .env file
LIGHTAPI_JWT_SECRET=dev-secret-key-change-in-production
LIGHTAPI_DATABASE_URL=sqlite:///auth_example.db
LIGHTAPI_DEBUG=true
```

### Production

```bash
# Production environment variables
export LIGHTAPI_JWT_SECRET="$(openssl rand -base64 32)"
export LIGHTAPI_DATABASE_URL="postgresql://user:pass@localhost/prod_db"
export LIGHTAPI_DEBUG=false
export LIGHTAPI_CORS_ORIGINS="https://yourdomain.com"
```

## Troubleshooting

### Common Issues

1. **"JWT secret key not configured"**
   ```bash
   export LIGHTAPI_JWT_SECRET="your-secret-key"
   ```

2. **Token always invalid**
   ```python
   # Check token format
   print(f"Token: {token}")
   
   # Verify secret key
   print(f"Secret: {config.jwt_secret}")
   ```

3. **CORS issues with authentication**
   ```python
   app.add_middleware([
       CORSMiddleware(
           allow_origins=["http://localhost:3000"],
           allow_headers=["Authorization", "Content-Type"]
       )
   ])
   ```

### Debug Authentication

```python
class DebugJWTAuth(JWTAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        print(f"Auth header: {auth_header}")
        
        if not auth_header:
            print("No Authorization header")
            return False
        
        try:
            result = super().authenticate(request)
            print(f"Authentication result: {result}")
            return result
        except Exception as e:
            print(f"Authentication error: {e}")
            return False
```

## Next Steps

- **[Middleware Example](middleware.md)** - Custom middleware patterns
- **[Validation Example](validation.md)** - Request validation
- **[Caching Example](caching.md)** - Performance optimization
- **[API Reference](../api-reference/auth.md)** - Authentication API details 