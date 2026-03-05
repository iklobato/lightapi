---
title: Advanced Role-Based Permissions
---

# Advanced Role-Based Permissions

Role-based access control using per-method authentication, `IsAdminUser`, and JWT claims.

## Setup

```bash
export LIGHTAPI_JWT_SECRET="your-secret-key"
```

## Full RBAC endpoint

```python
from lightapi import (
    LightApi, RestEndpoint, Field,
    Authentication, JWTAuthentication,
    IsAuthenticated, IsAdminUser, AllowAny,
)
from sqlalchemy import create_engine

class ArticleEndpoint(RestEndpoint):
    title:     str  = Field(min_length=1, max_length=255)
    content:   str
    published: bool = Field(default=False)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission={
                "GET":    AllowAny,        # public reads
                "POST":   IsAuthenticated, # logged-in users can create
                "PUT":    IsAuthenticated,
                "PATCH":  IsAuthenticated,
                "DELETE": IsAdminUser,     # only admins can delete
            },
        )

engine = create_engine("sqlite:///app.db")
app = LightApi(engine=engine)
app.register({"/articles": ArticleEndpoint})
app.run()
```

## Generating tokens with roles

```python
from lightapi.auth import JWTAuthentication

auth = JWTAuthentication()

# Regular user
user_token = auth.generate_token({"sub": "42", "is_admin": False})

# Admin user
admin_token = auth.generate_token({"sub": "1", "is_admin": True})
```

## Permission class reference

| Class | `has_permission` logic |
|-------|----------------------|
| `AllowAny` | Always `True` |
| `IsAuthenticated` | `request.state.user is not None` |
| `IsAdminUser` | `request.state.user["is_admin"] == True` |

## Custom permission class

```python
from starlette.requests import Request

class IsOwner:
    """Permit only if the JWT `sub` matches the resource owner."""
    def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        if not user:
            return False
        resource_id = request.path_params.get("id")
        # Compare user ID from JWT with the owner ID (simplified)
        return str(user.get("sub")) == str(resource_id)
```

Use in `Meta.authentication`:

```python
    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission={"GET": AllowAny, "DELETE": IsOwner},
        )
```

## E-commerce YAML example

```yaml
database:
  url: "${DATABASE_URL}"

defaults:
  authentication:
    backend: JWTAuthentication
    permission: IsAuthenticated

endpoints:
  - route: /products
    fields:
      name:     { type: str, max_length: 200 }
      price:    { type: float }
      active:   { type: bool, default: true }
    meta:
      methods:
        GET:    { authentication: { permission: AllowAny } }
        POST:   { authentication: { permission: IsAdminUser } }
        PUT:    { authentication: { permission: IsAdminUser } }
        DELETE: { authentication: { permission: IsAdminUser } }
      authentication:
        backend: JWTAuthentication

  - route: /orders
    fields:
      reference: { type: str }
      total:     { type: float }
    meta:
      methods: [GET, POST]
```

## Multi-resource setup

```python
from sqlalchemy import create_engine
from lightapi import LightApi

engine = create_engine("sqlite:///shop.db")
app = LightApi(engine=engine)

app.register({
    "/products": ProductEndpoint,
    "/orders":   OrderEndpoint,
    "/users":    UserEndpoint,
})
app.run()
```
