---
title: Authentication API Reference
description: Authentication and permission classes in LightAPI v2
---

# Authentication API Reference

## Overview

Authentication is per-endpoint and configured via `Meta.authentication`:

```python
from lightapi import (
    RestEndpoint,
    Authentication, JWTAuthentication, IsAuthenticated,
)

class PostEndpoint(RestEndpoint):
    title: str

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
        )
```

## `Authentication`

```python
from lightapi import Authentication
# or: from lightapi.config import Authentication

Authentication(
    backend: type | None = None,
    permission: type | dict[str, type] | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `backend` | `type \| None` | Authentication backend class. `None` = unauthenticated (allow all). |
| `permission` | `type \| dict[str, type] \| None` | Permission class applied to all methods, or a `{method: class}` dict for per-method control. `None` = `AllowAny`. |

## `JWTAuthentication`

JWT authentication using `Authorization: Bearer <token>` headers.

**Required:** `LIGHTAPI_JWT_SECRET` environment variable must be set.

```bash
export LIGHTAPI_JWT_SECRET="your-secret-key"
```

**Token format:**

```json
{
  "sub": "user-id",
  "is_admin": false,
  "exp": 1234567890
}
```

After successful authentication, the decoded payload is stored in `request.state.user`.

**Behaviour:**

- OPTIONS requests are always allowed (CORS preflight compatibility).
- Returns `401 Unauthorized` if the token is missing, malformed, or expired.

## Permission Classes

### `AllowAny`

```python
from lightapi import AllowAny
```

No authentication check. All requests are allowed. This is the default when `permission=None`.

### `IsAuthenticated`

```python
from lightapi import IsAuthenticated
```

Allows access only if the authentication backend returns `True` (valid credentials present).

### `IsAdminUser`

```python
from lightapi import IsAdminUser
```

Allows access only if the JWT payload contains `"is_admin": true`.

## Per-method permissions

Pass a `dict[str, type]` to apply different permission classes per HTTP method:

```python
from lightapi import Authentication, JWTAuthentication, IsAuthenticated, IsAdminUser, AllowAny

class ArticleEndpoint(RestEndpoint):
    title: str

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission={
                "GET":    AllowAny,
                "POST":   IsAuthenticated,
                "PUT":    IsAuthenticated,
                "PATCH":  IsAuthenticated,
                "DELETE": IsAdminUser,
            },
        )
```

## `BaseAuthentication`

Implement to create a custom authentication backend:

```python
from lightapi.auth import BaseAuthentication

class ApiKeyAuthentication(BaseAuthentication):
    def authenticate(self, request) -> bool:
        key = request.headers.get("X-Api-Key")
        return key == "expected-key"
```

## `BasePermission`

Implement to create a custom permission class:

```python
from lightapi.auth import BasePermission

class IsOwner(BasePermission):
    def has_permission(self, request) -> bool:
        user = getattr(request.state, "user", None)
        if not user:
            return False
        return str(user.get("sub")) == str(request.path_params.get("id"))
```

## Response codes

| Situation | Status |
|-----------|--------|
| Missing or invalid token | `401 Unauthorized` |
| Valid token, insufficient permission | `403 Forbidden` |
| OPTIONS request | Always `200` (CORS preflight) |
