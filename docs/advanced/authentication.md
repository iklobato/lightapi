---
title: Authentication
description: Protecting endpoints with JWT authentication and permission classes
---

# Authentication

LightAPI provides JWT-based authentication via the `Authentication` Meta option. Authentication is per-endpoint and composable with permission classes.

## Quick Start

```python
import os
from typing import Optional
from sqlalchemy import create_engine
from lightapi import (
    LightApi, RestEndpoint, Field,
    Authentication, JWTAuthentication, IsAuthenticated, IsAdminUser,
)

class PostEndpoint(RestEndpoint):
    title: str
    body: str
    author_id: Optional[int] = None

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
        )

engine = create_engine("sqlite:///app.db")
app = LightApi(engine=engine)
app.register({"/posts": PostEndpoint})
```

Any request that does not carry a valid `Authorization: Bearer <token>` header now receives `401 Unauthorized`.

## Authentication class

```python
from lightapi import Authentication, JWTAuthentication, IsAuthenticated

Authentication(
    backend=JWTAuthentication,   # Authentication backend class
    permission=IsAuthenticated,  # Permission class (or dict for per-method permissions)
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `backend` | `type \| None` | Authentication backend. `None` = public access. |
| `permission` | `type \| dict[str, type] \| None` | Permission class applied globally, or a `{method: class}` dict for per-method control. |

## JWTAuthentication

Authenticates requests using a `Bearer` token in the `Authorization` header.

**Required environment variable:**

```bash
export LIGHTAPI_JWT_SECRET="your-secret-key"
```

**Token format:**

```
Authorization: Bearer <jwt-token>
```

The token payload is stored in `request.state.user` after successful authentication.

### Generating tokens

LightAPI does not include a login endpoint — you generate tokens in your own code:

```python
import jwt, os, datetime

def make_token(user_id: int, is_admin: bool = False) -> str:
    return jwt.encode(
        {
            "sub": str(user_id),
            "is_admin": is_admin,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        },
        os.environ["LIGHTAPI_JWT_SECRET"],
        algorithm="HS256",
    )
```

## Permission Classes

### `AllowAny`

No authentication check — equivalent to having no `Meta.authentication`. Default when `permission` is `None`.

### `IsAuthenticated`

Allows access only if `JWTAuthentication.authenticate()` returns `True` (valid token present).

### `IsAdminUser`

Allows access only if the token payload contains `"is_admin": true`.

```python
from lightapi import Authentication, JWTAuthentication, IsAdminUser

class AdminEndpoint(RestEndpoint):
    name: str

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAdminUser,
        )
```

## Per-Method Permissions

Pass a `dict[str, type]` to `permission` to apply different rules per HTTP verb:

```python
from lightapi import (
    Authentication, JWTAuthentication,
    IsAuthenticated, IsAdminUser, AllowAny,
)

class ArticleEndpoint(RestEndpoint):
    title: str
    body: str

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission={
                "GET": AllowAny,        # public reads
                "POST": IsAuthenticated, # authenticated creates
                "PUT": IsAuthenticated,
                "PATCH": IsAuthenticated,
                "DELETE": IsAdminUser,  # admin-only deletes
            },
        )
```

## Custom Authentication Backend

Subclass `BaseAuthentication` to implement your own logic:

```python
from lightapi.auth import BaseAuthentication

class ApiKeyAuthentication(BaseAuthentication):
    def authenticate(self, request) -> bool:
        key = request.headers.get("X-Api-Key")
        return key == "my-secret-api-key"
```

Use it as the `backend`:

```python
class SecureEndpoint(RestEndpoint):
    value: str

    class Meta:
        authentication = Authentication(backend=ApiKeyAuthentication)
```

## Custom Permission Class

Subclass `BasePermission` to implement your own access control:

```python
from lightapi.auth import BasePermission

class IsOwner(BasePermission):
    def has_permission(self, request) -> bool:
        user = getattr(request.state, "user", None)
        if user is None:
            return False
        resource_owner_id = request.path_params.get("id")
        return str(user.get("sub")) == str(resource_owner_id)
```

## Public Endpoints

To make an endpoint fully public, either omit `Meta.authentication` or set:

```python
from lightapi import Authentication, AllowAny

class PublicEndpoint(RestEndpoint):
    name: str

    class Meta:
        authentication = Authentication(permission=AllowAny)
```

## CORS Preflight

OPTIONS requests are automatically allowed by `JWTAuthentication` without checking the token, ensuring CORS preflight requests always succeed.

## Complete Example

```python
import os
from typing import Optional
from sqlalchemy import create_engine
from lightapi import (
    LightApi, RestEndpoint, Field,
    Authentication, JWTAuthentication,
    IsAuthenticated, IsAdminUser, AllowAny,
)

os.environ.setdefault("LIGHTAPI_JWT_SECRET", "dev-secret")

class UserEndpoint(RestEndpoint):
    username: str = Field(min_length=3, unique=True)
    email: str = Field(unique=True)
    is_admin: Optional[bool] = None

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission={
                "GET": AllowAny,
                "POST": IsAdminUser,
                "PUT": IsAuthenticated,
                "PATCH": IsAuthenticated,
                "DELETE": IsAdminUser,
            },
        )

engine = create_engine("sqlite:///app.db")
app = LightApi(engine=engine)
app.register({"/users": UserEndpoint})
app.run()
```

```bash
# Unauthenticated read — allowed
curl http://localhost:8000/users

# Create without token — 401
curl -X POST http://localhost:8000/users \
     -H "Content-Type: application/json" \
     -d '{"username": "bob", "email": "bob@example.com"}'

# Create with admin token — 201
TOKEN=$(python -c "
import jwt, datetime
print(jwt.encode({'sub':'1','is_admin':True,'exp':datetime.datetime.utcnow()+datetime.timedelta(hours=1)},
    'dev-secret', algorithm='HS256'))
")
curl -X POST http://localhost:8000/users \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"username": "bob", "email": "bob@example.com"}'
```
