---
title: YAML Configuration Examples
---

# YAML Configuration Examples

`LightApi.from_config()` loads a `lightapi.yaml` validated by Pydantic v2.

## Declarative format (recommended)

Define endpoints, fields, and `Meta` options entirely in YAML — no Python classes needed.

```yaml
# lightapi.yaml
database:
  url: "${DATABASE_URL}"   # ${VAR} env-var substitution

cors_origins:
  - "https://myapp.com"

defaults:
  authentication:
    backend: JWTAuthentication
    permission: IsAuthenticated
    jwt_expiration: 3600
    jwt_extra_claims: [sub, email]
  pagination:
    style: page_number
    page_size: 20

middleware:
  - CORSMiddleware

auth:
  auth_path: /auth
  login_validator: myapp.validators.validate_login

endpoints:
  - route: /products
    fields:
      name:     { type: str, max_length: 200 }
      price:    { type: float }
      category: { type: str }
      active:   { type: bool, default: true }
    meta:
      methods: [GET, POST, PUT, DELETE]
      filtering:
        fields:   [category, active]
        ordering: [price]
      authentication:
        permission: AllowAny   # override global default for this endpoint

  - route: /orders
    fields:
      reference: { type: str }
      total:     { type: float }
    meta:
      methods: [GET, POST]
```

```python
from lightapi import LightApi

app = LightApi.from_config("lightapi.yaml")
app.run()
```

## Field types

| `type` value | Python type | Notes |
|-------------|-------------|-------|
| `str` | `str` | |
| `int` | `int` | |
| `float` | `float` | |
| `bool` | `bool` | |
| `datetime` | `datetime.datetime` | |
| `Decimal` | `Decimal` | |

## Field constraints in YAML

```yaml
fields:
  name:  { type: str, min_length: 1, max_length: 200 }
  price: { type: float }
  sku:   { type: str, unique: true, index: true }
  qty:   { type: int, default: 0, optional: true }
```

## Per-method authentication

Use the dict form of `methods` for different permissions per verb:

```yaml
endpoints:
  - route: /articles
    fields:
      title:   { type: str }
      content: { type: str }
    meta:
      methods:
        GET:
          authentication: { permission: AllowAny }
        POST:
          authentication: { permission: IsAuthenticated }
        DELETE:
          authentication: { permission: IsAdminUser }
      authentication:
        backend: JWTAuthentication
```

## Database table reflection

```yaml
endpoints:
  - route: /legacy-orders
    reflect: true
```

## Environment variable substitution

Any `${VAR}` placeholder is replaced at load time. A missing variable raises `ConfigurationError` immediately:

```yaml
database:
  url: "${DATABASE_URL}"
```

```bash
export DATABASE_URL="postgresql+psycopg2://user:pass@localhost/mydb"
python -c "from lightapi import LightApi; LightApi.from_config('lightapi.yaml').run()"
```

## YAML schema reference

| Field | Type | Description |
|-------|------|-------------|
| `database.url` | string | SQLAlchemy URL. Supports `${VAR}` substitution. |
| `cors_origins` | list | CORS allowed origins. |
| `defaults.authentication.backend` | string | Auth backend class name (`JWTAuthentication`, `BasicAuthentication`). |
| `defaults.authentication.permission` | string | Permission class name. |
| `defaults.authentication.jwt_expiration` | int | JWT token expiration in seconds (JWT only). |
| `defaults.authentication.jwt_extra_claims` | list | Claims to include in token payload (JWT only). |
| `auth.auth_path` | string | Path prefix for `/login` and `/token` (default `/auth`). |
| `auth.login_validator` | string | Dotted path to credential validator callable (e.g. `myapp.validators.check_user`). |
| `defaults.pagination.style` | string | `page_number` or `cursor`. |
| `defaults.pagination.page_size` | int | Rows per page. |
| `middleware` | list | Class names resolved at startup. |
| `endpoints[].route` | string | URL prefix. |
| `endpoints[].fields` | object | Field definitions. |
| `endpoints[].meta.methods` | list or dict | HTTP verbs or per-method auth dict. |
| `endpoints[].meta.filtering` | object | `fields`, `search`, `ordering`. |
| `endpoints[].meta.pagination` | object | `style`, `page_size`. |
| `endpoints[].reflect` | bool | Reflect existing table. |
