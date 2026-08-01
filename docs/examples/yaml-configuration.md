---
title: YAML Configuration Examples
---

# YAML Configuration Examples

`LightApi.from_config()` loads a `lightapi.yaml` file, validates it with Pydantic v2, and builds a fully configured ASGI application — no Python endpoint classes required.

## Quick start

```yaml
# lightapi.yaml
database:
  url: "${DATABASE_URL}"

cors_origins:
  - "https://myapp.com"

mode: async

defaults:
  authentication:
    backend: JWTAuthentication
    permission: IsAuthenticated
    jwt_expiration: 3600
    jwt_extra_claims: [sub, email]
    jwt_algorithm: HS256
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
      name:     { type: str,  min_length: 1, max_length: 200 }
      price:    { type: float, gt: 0 }
      sku:      { type: str,  unique: true, index: true }
      qty:      { type: int,  default: 0,   optional: true }
      active:   { type: bool, default: true }
    meta:
      methods: [GET, POST, PUT, DELETE]
      filtering:
        fields:   [active]
        search:   [name]
        ordering: [price, name]
      authentication:
        permission: AllowAny   # overrides the global IsAuthenticated for this endpoint

  - route: /orders
    fields:
      reference: { type: str }
      total:     { type: float }
    meta:
      methods: [GET, POST]
```

```python
# main.py
from lightapi import LightApi

app = LightApi.from_config("lightapi.yaml")
app.run()
```

```bash
export DATABASE_URL="postgresql+psycopg2://user:pass@localhost/shop"
python main.py
```

---

## Database URL and environment-variable substitution

Any `${VAR}` placeholder in `database.url` is resolved from the process environment at load time. A missing variable raises `ConfigurationError` immediately — the server never starts with a broken config.

```yaml
database:
  url: "${DATABASE_URL}"
```

The substitution supports exactly the `${VAR}` form. Inline references such as `prefix_${VAR}_suffix` are not expanded — the entire value must be the placeholder.

Supported SQLAlchemy URL schemes:

```yaml
# SQLite (sync)
database:
  url: "sqlite:///./local.db"

# PostgreSQL (sync)
database:
  url: "postgresql+psycopg2://user:pass@localhost/mydb"

# PostgreSQL (async — requires mode: async)
database:
  url: "postgresql+asyncpg://user:pass@localhost/mydb"

# MySQL (sync)
database:
  url: "mysql+pymysql://user:pass@localhost/mydb"
```

---

## mode

Controls whether LightAPI uses sync or async SQLAlchemy sessions. When omitted, mode is auto-detected from endpoint method signatures.

```yaml
mode: async   # "sync" | "async"
```

`mode: async` requires an `AsyncEngine` and async dialect drivers (e.g. `asyncpg`, `aiosqlite`). Pass an engine override when the URL alone is insufficient:

```python
from sqlalchemy.ext.asyncio import create_async_engine
from lightapi import LightApi

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/mydb")
app = LightApi.from_config("lightapi.yaml", engine=engine)
app.run()
```

---

## cors_origins

List of allowed CORS origins. Adds `CORSMiddleware` with `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.

```yaml
cors_origins:
  - "https://myapp.com"
  - "https://staging.myapp.com"
  - "http://localhost:3000"
```

---

## auth block

Configures the login endpoint (`POST /auth/login` and `POST /auth/token`) used by `JWTAuthentication` and `BasicAuthentication`.

```yaml
auth:
  auth_path: /auth                              # prefix; default is /auth
  login_validator: myapp.validators.validate_login
```

`login_validator` must be a dotted path to a **synchronous** callable that accepts exactly two required positional arguments (`username`, `password`) and returns a `dict` on success or `None` / raises an exception on failure.

```python
# myapp/validators.py

def validate_login(username: str, password: str) -> dict | None:
    """Return a claims dict on success; raise ValueError or return None on failure."""
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        raise ValueError("Invalid credentials")
    return {"sub": str(user.id), "email": user.email, "role": user.role}
```

Rules enforced at startup:
- Must be importable at the dotted path.
- Must be synchronous (not `async def`).
- Must have exactly 2 required positional parameters.
- Any exception raised during login → HTTP 401.

---

## defaults block

Global defaults applied to every endpoint unless that endpoint provides its own override.

```yaml
defaults:
  authentication:
    backend: JWTAuthentication         # JWTAuthentication | BasicAuthentication
    permission: IsAuthenticated        # AllowAny | IsAuthenticated | IsAdminUser
    jwt_expiration: 3600               # seconds; JWT only
    jwt_extra_claims: [sub, email]     # additional JWT payload claims; JWT only
    jwt_algorithm: HS256               # HS256/HS384/HS512/RS256/RS384/RS512/ES256/ES384/ES512
  pagination:
    style: page_number                 # page_number | cursor
    page_size: 20
```

An endpoint's own `meta.authentication` or `meta.pagination` block overrides the corresponding default entirely — individual sub-keys are not merged.

---

## middleware

Class names resolved from the built-in registry or as dotted import paths. Applied to every request in order (pre) and in reverse order (post).

```yaml
middleware:
  - CORSMiddleware
  - AuthenticationMiddleware
  - myapp.middleware.RequestIdMiddleware   # dotted path for custom middleware
```

Built-in middleware names: `Middleware`, `CORSMiddleware`, `AuthenticationMiddleware`.

---

## Field types and constraints

Every field in `fields:` requires a `type` key. All other keys are forwarded as constraints to the underlying `Field()` definition.

### Supported types

| `type` value | Python type        |
|--------------|--------------------|
| `str`        | `str`              |
| `int`        | `int`              |
| `float`      | `float`            |
| `bool`       | `bool`             |
| `datetime`   | `datetime.datetime` |
| `Decimal`    | `Decimal`          |
| `decimal`    | `Decimal`          |

### Supported constraints

| Key             | Applies to        | Description                                      |
|-----------------|-------------------|--------------------------------------------------|
| `min_length`    | `str`             | Minimum string length.                           |
| `max_length`    | `str`             | Maximum string length.                           |
| `gt`            | numeric           | Value must be strictly greater than.             |
| `ge`            | numeric           | Value must be greater than or equal to.          |
| `lt`            | numeric           | Value must be strictly less than.                |
| `le`            | numeric           | Value must be less than or equal to.             |
| `default`       | any               | Default value when the field is omitted.         |
| `optional`      | any               | `true` makes the field `Optional[T]` (nullable). |
| `unique`        | any               | Adds a UNIQUE constraint to the database column. |
| `index`         | any               | Adds an index to the database column.            |
| `foreign_key`   | `int` (usually)   | SQLAlchemy foreign key (e.g. `"users.id"`).      |
| `decimal_places`| `Decimal`         | Number of decimal places for `Decimal` columns.  |

### Complete field example

```yaml
endpoints:
  - route: /items
    fields:
      name:        { type: str,     min_length: 1, max_length: 200 }
      description: { type: str,     optional: true }
      price:       { type: Decimal, gt: 0, decimal_places: 2 }
      qty:         { type: int,     ge: 0, default: 0 }
      weight_kg:   { type: float,   gt: 0, lt: 1000 }
      active:      { type: bool,    default: true }
      expires_at:  { type: datetime, optional: true }
      sku:         { type: str,     unique: true, index: true, max_length: 50 }
      category_id: { type: int,     foreign_key: "categories.id" }
    meta:
      methods: [GET, POST, PUT, PATCH, DELETE]
```

---

## meta block

Every endpoint's behavior is controlled by its `meta:` block.

### methods — list form

```yaml
meta:
  methods: [GET, POST, PUT, PATCH, DELETE]
```

All listed verbs use the same authentication setting from `meta.authentication` (or the global default).

### methods — dict form (per-method auth)

Use a dict when different verbs need different permissions:

```yaml
endpoints:
  - route: /articles
    fields:
      title:   { type: str, max_length: 300 }
      content: { type: str }
      draft:   { type: bool, default: true }
    meta:
      methods:
        GET:
          authentication: { permission: AllowAny }
        POST:
          authentication: { permission: IsAuthenticated }
        DELETE:
          authentication: { permission: IsAdminUser }
      authentication:
        backend: JWTAuthentication   # shared backend for all methods
```

Methods not listed in the dict are not registered (no route is created for them). Methods listed without an `authentication` key inherit the endpoint-level `meta.authentication`, which in turn falls back to `defaults.authentication`.

### meta.authentication

Override global auth for a single endpoint:

```yaml
meta:
  authentication:
    backend: JWTAuthentication
    permission: IsAuthenticated
    jwt_expiration: 900
    jwt_extra_claims: [sub]
    jwt_algorithm: HS512
```

Set `permission: AllowAny` to make an endpoint fully public while keeping auth configured globally.

### meta.filtering

LightAPI supports three filter backends. When `backends:` is omitted, backends are **auto-selected** based on which lists are populated:

- `fields` present → `FieldFilter` added
- `search` present → `SearchFilter` added
- `ordering` present → `OrderingFilter` added

**Auto-backend selection (recommended):**

```yaml
meta:
  filtering:
    fields:   [category, active]   # exact-match: ?category=books
    search:   [name, description]  # LIKE search: ?search=laptop
    ordering: [price, created_at]  # sort: ?ordering=-price or ?ordering=price,name
```

**Explicit backend list:**

```yaml
meta:
  filtering:
    backends: [FieldFilter, SearchFilter, OrderingFilter]
    fields:   [category, active]
    search:   [name]
    ordering: [price]
```

Use the explicit `backends:` list when you need a strict subset — for example, `SearchFilter` without `FieldFilter`:

```yaml
meta:
  filtering:
    backends: [SearchFilter]
    search:   [name, description]
```

### meta.pagination — page_number style

```yaml
meta:
  pagination:
    style: page_number
    page_size: 25
```

Request: `GET /products?page=2&page_size=25`

Response shape:

```json
{
  "count": 120,
  "pages": 5,
  "next": "http://localhost/products?page=3",
  "previous": "http://localhost/products?page=1",
  "results": [...]
}
```

### meta.pagination — cursor style

```yaml
meta:
  pagination:
    style: cursor
    page_size: 50
```

Request: `GET /events?cursor=<opaque-base64-token>`

Response shape:

```json
{
  "next": "<next-cursor-token>",
  "previous": null,
  "results": [...]
}
```

Cursor pagination requires an `id` column (integer primary key). The cursor token is `base64(json({"id": last_id}))`.

### meta.cache

Caches GET responses in Redis. Write operations (POST, PUT, PATCH, DELETE) automatically invalidate all cache entries for the endpoint.

```yaml
meta:
  cache:
    ttl: 120   # seconds; must be >= 1
```

The cache key includes the endpoint class name, URL path, and full query string, so filtered and paginated results are cached independently. If Redis is unreachable at startup, a `RuntimeWarning` is emitted and caching is silently skipped per request.

### meta.serializer — unified field list

Limit which fields appear in all responses (reads) and are accepted in request bodies (writes):

```yaml
meta:
  serializer:
    fields: [id, name, price, active]
```

### meta.serializer — separate read and write lists

```yaml
meta:
  serializer:
    read:  [id, name, price, active, created_at]
    write: [name, price, active]
```

`fields` and `read`/`write` are mutually exclusive — using both raises `ConfigurationError` at startup.

### meta.table

Override the database table name for an endpoint. Required when `reflect: true` and the table name differs from the default (`<classname>s` lowercased).

```yaml
meta:
  table: legacy_product_catalog
```

---

## Table reflection

Reflect an existing database table instead of defining fields:

```yaml
endpoints:
  - route: /legacy-orders
    reflect: true
    meta:
      table: legacy_orders_2019    # required when table name != default
      methods: [GET]
```

When `reflect: true` the `fields:` block is ignored. The endpoint schema is derived from the existing table columns at startup.

---

## Complete real-world example

This single YAML file shows every supported feature together:

```yaml
# lightapi.yaml — complete example
database:
  url: "${DATABASE_URL}"

mode: async

cors_origins:
  - "https://myapp.com"
  - "http://localhost:3000"

defaults:
  authentication:
    backend: JWTAuthentication
    permission: IsAuthenticated
    jwt_expiration: 3600
    jwt_extra_claims: [sub, email]
    jwt_algorithm: HS256
  pagination:
    style: page_number
    page_size: 20

middleware:
  - CORSMiddleware

auth:
  auth_path: /auth
  login_validator: myapp.validators.validate_login

endpoints:
  # Public product catalog — AllowAny overrides global IsAuthenticated
  - route: /products
    fields:
      name:        { type: str,     min_length: 1, max_length: 200 }
      description: { type: str,     optional: true }
      price:       { type: Decimal, gt: 0, decimal_places: 2 }
      qty:         { type: int,     ge: 0, default: 0 }
      active:      { type: bool,    default: true }
      sku:         { type: str,     unique: true, index: true }
      category_id: { type: int,     foreign_key: "categories.id" }
    meta:
      methods: [GET, POST, PUT, DELETE]
      authentication:
        permission: AllowAny
      filtering:
        fields:   [active, category_id]
        search:   [name, description]
        ordering: [price, name]
      pagination:
        style: page_number
        page_size: 50
      cache:
        ttl: 300
      serializer:
        read:  [id, name, price, active, sku]
        write: [name, description, price, qty, active, sku, category_id]
      table: product_catalog

  # Per-method auth: public reads, authenticated writes, admin-only deletes
  - route: /articles
    fields:
      title:      { type: str,  max_length: 300 }
      body:       { type: str }
      published:  { type: bool, default: false }
      views:      { type: int,  default: 0, optional: true }
      created_at: { type: datetime, optional: true }
    meta:
      methods:
        GET:
          authentication: { permission: AllowAny }
        POST:
          authentication: { permission: IsAuthenticated }
        PUT:
          authentication: { permission: IsAuthenticated }
        DELETE:
          authentication: { permission: IsAdminUser }
      authentication:
        backend: JWTAuthentication
      filtering:
        fields:   [published]
        search:   [title, body]
        ordering: [created_at, views]
      pagination:
        style: cursor
        page_size: 10

  # Cursor-paginated event log with explicit backends
  - route: /events
    fields:
      event_type: { type: str, max_length: 50 }
      payload:    { type: str }
      occurred_at:{ type: datetime }
      user_id:    { type: int, foreign_key: "users.id", optional: true }
    meta:
      methods: [GET, POST]
      filtering:
        backends: [FieldFilter, OrderingFilter]
        fields:   [event_type, user_id]
        ordering: [occurred_at]
      pagination:
        style: cursor
        page_size: 100
      cache:
        ttl: 60

  # Legacy table — reflected from DB, no field definitions needed
  - route: /legacy-invoices
    reflect: true
    meta:
      table: invoices_archive_2020
      methods: [GET]
```

```python
# main.py
from sqlalchemy.ext.asyncio import create_async_engine
from lightapi import LightApi

# kwargs override YAML-derived values
engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/shop")
app = LightApi.from_config("lightapi.yaml", engine=engine)
app.run(host="0.0.0.0", port=8000)
```

---

## login_validator Python example

```python
# myapp/validators.py
from myapp.models import User
from myapp.security import verify_password

def validate_login(username: str, password: str) -> dict | None:
    """Validate credentials and return a JWT claims dict, or raise on failure.

    Rules:
    - Return a dict on success; the keys become additional JWT payload claims.
    - Return None or raise any exception to trigger HTTP 401.
    - Must be synchronous; async validators are rejected at startup.
    - Must accept exactly 2 required positional arguments.
    """
    user = User.get_by_username(username)
    if user is None or not verify_password(password, user.password_hash):
        raise ValueError("Invalid username or password")
    if not user.is_active:
        raise PermissionError("Account is disabled")
    return {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
    }
```

Reference in YAML:

```yaml
auth:
  auth_path: /auth
  login_validator: myapp.validators.validate_login
```

Successful login returns:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## Behavior notes

### SearchFilter — `%` and `_` treated as literals

`SearchFilter` escapes SQL LIKE special characters before constructing the `ILIKE` clause. A user searching for `50%` or `file_name` matches those literal strings — there is no way to inject a wildcard through the `?search=` parameter.

### OrderingFilter — explicit whitelist required

`OrderingFilter` only sorts on columns explicitly listed in `filtering.ordering`. An empty or omitted `ordering:` list disables ordering entirely, even if `OrderingFilter` is listed under `backends:`. Client-supplied `?ordering=` values that name non-whitelisted columns are silently ignored.

```yaml
filtering:
  ordering: []   # ordering disabled — ?ordering= has no effect
```

### AllowAny bypasses backend authentication

When `permission: AllowAny` is set (endpoint-level or per-method), the authentication backend is **not called**. No token or credential is validated. Use `AllowAny` only for genuinely public endpoints.

### PATCH `null` clears Optional fields

A `PATCH` request with `"field": null` sets that column to `NULL` in the database, provided the field is declared `optional: true`. Fields without `optional: true` reject `null` values with a 422 validation error.

### Cache auto-invalidated on writes

Any non-GET request (POST, PUT, PATCH, DELETE) automatically invalidates all cache entries whose key prefix matches `lightapi:<EndpointClassName>:`. The cache TTL controls read freshness only; writes always clear stale data immediately.

### login_validator exceptions → 401

Any exception raised inside `login_validator` — regardless of type — causes the login endpoint to return HTTP 401 with `{"detail": "Authentication credentials invalid."}`. The exception is not re-raised or logged to the client.

---

## YAML schema reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `database.url` | string | — | SQLAlchemy connection URL. Supports `${VAR}` substitution. Required unless `engine=` is passed to `from_config()`. |
| `mode` | string | auto | `"sync"` or `"async"`. Auto-detected from endpoint methods when omitted. |
| `cors_origins` | list[string] | `[]` | Allowed CORS origins. |
| `middleware` | list[string] | `[]` | Built-in or dotted-path middleware class names. |
| `auth.auth_path` | string | `"/auth"` | URL prefix for `/login` and `/token`. |
| `auth.login_validator` | string | — | Dotted path to sync credential validator `(username, password) -> dict \| None`. |
| `defaults.authentication.backend` | string | — | Auth backend class name: `JWTAuthentication` or `BasicAuthentication`. |
| `defaults.authentication.permission` | string | — | Permission class: `AllowAny`, `IsAuthenticated`, `IsAdminUser`. |
| `defaults.authentication.jwt_expiration` | int | `3600` | JWT expiry in seconds. JWT only. |
| `defaults.authentication.jwt_extra_claims` | list[string] | `[]` | Additional claims included in JWT payload. JWT only. |
| `defaults.authentication.jwt_algorithm` | string | `HS256` | JWT signing algorithm. Valid: HS256/HS384/HS512/RS256/RS384/RS512/ES256/ES384/ES512. |
| `defaults.pagination.style` | string | `page_number` | `page_number` or `cursor`. |
| `defaults.pagination.page_size` | int | `20` | Rows per page. |
| `endpoints[].route` | string | — | URL prefix (e.g. `/products`). Required. |
| `endpoints[].reflect` | bool | `false` | Reflect schema from an existing database table. |
| `endpoints[].fields` | object | `{}` | Field definitions. Ignored when `reflect: true`. |
| `endpoints[].fields.<name>.type` | string | — | One of: `str`, `int`, `float`, `bool`, `datetime`, `Decimal`. Required. |
| `endpoints[].fields.<name>.optional` | bool | `false` | Makes the field `Optional[T]` (nullable). |
| `endpoints[].fields.<name>.default` | any | — | Default value when the field is omitted. |
| `endpoints[].fields.<name>.min_length` | int | — | Minimum string length. `str` only. |
| `endpoints[].fields.<name>.max_length` | int | — | Maximum string length. `str` only. |
| `endpoints[].fields.<name>.gt` | number | — | Value must be strictly greater than. Numeric types. |
| `endpoints[].fields.<name>.ge` | number | — | Value must be greater than or equal to. Numeric types. |
| `endpoints[].fields.<name>.lt` | number | — | Value must be strictly less than. Numeric types. |
| `endpoints[].fields.<name>.le` | number | — | Value must be less than or equal to. Numeric types. |
| `endpoints[].fields.<name>.unique` | bool | `false` | Adds a UNIQUE database constraint. |
| `endpoints[].fields.<name>.index` | bool | `false` | Adds a database index. |
| `endpoints[].fields.<name>.foreign_key` | string | — | Foreign key reference (e.g. `"users.id"`). |
| `endpoints[].fields.<name>.decimal_places` | int | — | Decimal precision. `Decimal` only. |
| `endpoints[].meta.methods` | list[string] or dict | `[]` | HTTP verbs as list, or dict of `{VERB: {authentication: ...}}`. |
| `endpoints[].meta.authentication.backend` | string | — | Auth backend override for this endpoint. |
| `endpoints[].meta.authentication.permission` | string | — | Permission class override for this endpoint. |
| `endpoints[].meta.authentication.jwt_expiration` | int | — | JWT expiry override for this endpoint. |
| `endpoints[].meta.authentication.jwt_extra_claims` | list[string] | — | JWT extra claims override for this endpoint. |
| `endpoints[].meta.authentication.jwt_algorithm` | string | — | JWT algorithm override for this endpoint. |
| `endpoints[].meta.filtering.backends` | list[string] | auto | Explicit filter backends: `FieldFilter`, `SearchFilter`, `OrderingFilter`. |
| `endpoints[].meta.filtering.fields` | list[string] | `[]` | Exact-match filter fields. Auto-enables `FieldFilter`. |
| `endpoints[].meta.filtering.search` | list[string] | `[]` | ILIKE search fields (`?search=`). Auto-enables `SearchFilter`. |
| `endpoints[].meta.filtering.ordering` | list[string] | `[]` | Allowed ordering fields (`?ordering=`). Auto-enables `OrderingFilter`. Empty list disables ordering. |
| `endpoints[].meta.pagination.style` | string | from defaults | `page_number` or `cursor`. |
| `endpoints[].meta.pagination.page_size` | int | from defaults | Rows per page. |
| `endpoints[].meta.cache.ttl` | int | `60` | Response cache TTL in seconds. Requires Redis. Writes auto-invalidate. |
| `endpoints[].meta.serializer.fields` | list[string] | — | Fields included in all responses and accepted in all request bodies. Mutually exclusive with `read`/`write`. |
| `endpoints[].meta.serializer.read` | list[string] | — | Fields included in GET responses only. |
| `endpoints[].meta.serializer.write` | list[string] | — | Fields accepted in POST/PUT/PATCH request bodies only. |
| `endpoints[].meta.table` | string | — | Override database table name. Required when `reflect: true` and table name differs from default. |
