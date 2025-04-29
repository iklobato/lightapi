---
title: Authentication Implementation
---

LightAPI provides a pluggable authentication system via the `authentication_class` configuration on any `RestEndpoint`. By default, LightAPI includes a JWT-based authenticator.

## JWTAuthentication

The `JWTAuthentication` class implements `BaseAuthentication` and uses PyJWT under the hood.

```python
from lightapi.auth import JWTAuthentication

# Generate a token for a user
token = JWTAuthentication.generate_token({"user_id": 1, "role": "admin"})

# The token payload will include an expiration timestamp by default (1 hour).
```

When you protect an endpoint, `request.user` is populated with the decoded token payload:

```python
from lightapi import LightApi
from lightapi.rest import RestEndpoint
from lightapi.auth import JWTAuthentication

class ProtectedEndpoint(RestEndpoint):
    class Configuration:
        authentication_class = JWTAuthentication

    async def get(self, request):
        # If authentication fails, a 401 response is returned.
        user = request.user  # Dict containing user_id and role
        return {"message": f"Hello, user {user['user_id']}"}

app = LightApi()
app.register({"/protected": ProtectedEndpoint})
```

### Configuration Options

- `secret_key` (str): The shared secret for encoding/decoding tokens. Override by subclassing or setting environment variable.
- `algorithm` (str): JWT algorithm (default: `HS256`).
- `expiration` (int): Token expiration in seconds (default: `3600`).

### Error Handling

- If the `Authorization` header is missing or malformed, a 401 Unauthorized response is returned.
- Invalid or expired tokens also yield a 401 response.
