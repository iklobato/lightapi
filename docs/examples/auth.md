---
title: Authentication Examples
---

# Authentication Examples

## JWT Authentication — quick start

```bash
export LIGHTAPI_JWT_SECRET="your-secret-key"
```

```python
from sqlalchemy import create_engine
from lightapi import (
    LightApi, RestEndpoint, Field,
    Authentication, JWTAuthentication, IsAuthenticated,
)

class PostEndpoint(RestEndpoint):
    title: str
    body:  str

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
        )

engine = create_engine("sqlite:///app.db")
app = LightApi(engine=engine)
app.register({"/posts": PostEndpoint})
app.run()
```

All requests to `/posts` now require `Authorization: Bearer <token>`.

## Generating tokens

`JWTAuthentication` ships with a `generate_token` method:

```python
from lightapi.auth import JWTAuthentication

auth = JWTAuthentication()
token = auth.generate_token({"sub": "42", "is_admin": False})
print(token)
```

## Per-method permissions

Allow `GET` for everyone, restrict `POST` / `DELETE` to authenticated and admin users:

```python
from lightapi import (
    RestEndpoint,
    Authentication, JWTAuthentication,
    IsAuthenticated, IsAdminUser, AllowAny,
)

class ArticleEndpoint(RestEndpoint):
    title:   str
    content: str

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

## Permission classes

| Class | Behaviour |
|-------|-----------|
| `AllowAny` | Permits all requests. |
| `IsAuthenticated` | Requires a decoded JWT in `request.state.user`. |
| `IsAdminUser` | Requires `request.state.user["is_admin"] == True`. |

## Accessing the authenticated user

After successful JWT authentication, the decoded payload is available in `request.state.user`:

```python
from starlette.responses import JSONResponse

class ProfileEndpoint(RestEndpoint):
    bio: str

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
        )

    def create(self, data: dict) -> JSONResponse:
        # Inject user id from JWT into the record
        from lightapi.lightapi import _get_current_request  # noqa
        # Use a custom queryset or override to access request.state.user
        return super().create(data)
```

For access to `request` inside `create` / `update`, override the method taking `request` directly:

```python
    async def _create_async(self, data: dict) -> JSONResponse:
        request = self._current_request
        user_id = request.state.user.get("sub")
        data["user_id"] = user_id
        return await super()._create_async(data)
```

## Global authentication default via YAML

```yaml
database:
  url: "${DATABASE_URL}"

defaults:
  authentication:
    backend: JWTAuthentication
    permission: IsAuthenticated

endpoints:
  - route: /posts
    fields:
      title: { type: str }
      body:  { type: str }
    meta:
      methods: [GET, POST, DELETE]

  - route: /public
    fields:
      label: { type: str }
    meta:
      methods: [GET]
      authentication:
        permission: AllowAny   # override the global default
```
