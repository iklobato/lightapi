# Authentication Reference

The Authentication module provides tools for implementing secure authentication in LightAPI applications.

## Authentication Methods

### JWT Authentication

```python
from lightapi.auth import JWTAuth

auth = JWTAuth(secret_key='your-secret-key')
```

### Basic Authentication

```python
from lightapi.auth import BasicAuth

auth = BasicAuth()
```

## User Authentication

### Login

```python
@app.route('/login')
def login(request):
    username = request.json.get('username')
    password = request.json.get('password')
    
    user = auth.authenticate(username, password)
    if user:
        token = auth.generate_token(user)
        return {'token': token}
    return {'error': 'Invalid credentials'}, 401
```

### Token Verification

```python
@app.route('/protected')
@auth.required
def protected_route(request):
    return {'message': 'This is a protected route'}
```

## User Management

### Password Hashing

```python
from lightapi.auth import hash_password, verify_password

hashed = hash_password('password123')
is_valid = verify_password('password123', hashed)
```

### User Creation

```python
from lightapi.auth import create_user

user = create_user(
    username='john',
    password='password123',
    email='john@example.com'
)
```

## Examples

### Complete Authentication Setup

```python
from lightapi import LightAPI
from lightapi.auth import JWTAuth, hash_password

app = LightAPI()
auth = JWTAuth(secret_key='your-secret-key')

@app.route('/register')
def register(request):
    user_data = request.json
    user_data['password'] = hash_password(user_data['password'])
    user = create_user(**user_data)
    return {'message': 'User created successfully'}

@app.route('/login')
def login(request):
    user = auth.authenticate(
        request.json['username'],
        request.json['password']
    )
    if user:
        token = auth.generate_token(user)
        return {'token': token}
    return {'error': 'Invalid credentials'}, 401

@app.route('/protected')
@auth.required
def protected_route(request):
    return {'message': 'This is a protected route'}
```

## Best Practices

1. Always use HTTPS for authentication endpoints
2. Implement proper password hashing
3. Use secure token generation and validation
4. Implement token expiration
5. Use secure session management

## See Also

- [Core API](core.md) - Core framework functionality
- [REST API](rest.md) - REST endpoint implementation
- [Models](models.md) - User model definition 