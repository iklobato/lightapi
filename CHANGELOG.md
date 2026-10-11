# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions align with [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Deprecated
- **`LightApi.from_dict`** emits a `DeprecationWarning` and is removed in 0.2.0. Use
  `RestEndpoint` subclasses with `register()`, or `from_config()` with a YAML file.

### Changed
- **The authentication backend is built once per route**, on the first request that needs
  it, instead of once per request. A backend subclass with its own `__init__` is therefore
  instantiated once. JWT settings and the secret are still read on every request.
- **A permission class decides whether login is required**: `BasePermission` has
  `requires_authentication = True` and `AllowAny` sets it to `False`. The only visible
  difference: a subclass of `AllowAny` used as a permission no longer forces authentication
  (before, only `AllowAny` itself, by identity, made a method public).
- **`/auth/login` with a body that is not valid UTF-8 returns 422** (it was a 500); a body
  that is not JSON still returns the same 422.
- **`Meta.reflect` rejects unknown values**: anything other than `True`, `False`, `"full"`
  or `"partial"` now raises `ConfigurationError` when the class is defined. Before, a value
  such as `"yes"` was silently treated as "not reflected" and produced a table with only the
  automatic columns.
- **Sync CRUD runs in a worker thread**: with a sync `Engine`, `list`, `retrieve`,
  `create`, `update`, `destroy` and the response-cache calls ran on the event loop
  thread, so one slow query held up every other request on that worker. They now
  go through `starlette.concurrency.run_in_threadpool`. Engines on `StaticPool` or
  `SingletonThreadPool` (in-memory SQLite) still run in place, because those pools
  cannot be shared across threads.

### Removed (internal, no public name affected)
- `RestEndpoint._meta["reflect"]`: the key was written but never read; `Meta.reflect` is
  read from the class itself.
- `lightapi.constants.HTTPStatus`: a copy of eleven members of the standard library's
  `http.HTTPStatus`, which the package now uses directly. Status codes in responses are
  unchanged.
- `lightapi.auth_checker` and `lightapi.middleware_runner`: `EndpointGuard` and the
  middleware runner (now `MiddlewareChain`) live in `lightapi.endpoint_handler`, the only
  module that used them.
- `lightapi.cache_helper` and the module functions `lightapi.cache.get_cached`,
  `set_cached` and `_ping_redis`: the response cache is `lightapi.cache.EndpointCache`
  (built once per route) over `RedisCacheBackend.shared()`, the process-wide client that is
  still created on first use. `lightapi.cache.invalidate_cache_prefix` stays.
- `lightapi.yaml_loader`, `lightapi.yaml_names` and `lightapi.yaml_schema`: the YAML
  document's models and the code that turns them into endpoints now live together in
  `lightapi.yaml_config` (`LightAPIConfig.from_file(...).build_app(...)`,
  `LightAPIConfig.resolve_name`). The YAML format is unchanged.
- `lightapi._dict_config_loader.load_from_dict`: `LightApi.from_dict` (deprecated) now goes
  through `DictConfig` in the same module.

### Fixed
- **`Meta.cache` was ignored on async engines**: cached GETs and cache invalidation
  only ran on the sync path, so an app on an `AsyncEngine` never read or wrote the
  cache. Both engine kinds now use it. The Redis calls run in a worker thread.
- **Sync verb overrides were ignored**: a plain `def get(self, request)` (or `post`,
  `put`, `patch`, `delete`) on an endpoint was skipped and the built-in CRUD ran
  instead; only `async def` overrides were served. Both are served now, on sync and
  async engines. A column that happens to be called `post` or `get` is still a
  column, not an override.
- **`/auth/login` ignored a backend's `validate_credentials`**: the login route
  always validated through a bare `JWTAuthentication()`, so overriding
  `validate_credentials()` on a subclass (the README's "custom authentication")
  never ran and login returned `401`. The route now uses the backend the endpoint
  configured, sync or `async def`. An app-level `login_validator` still wins.
- **Auth settings were dropped for backend subclasses**: `jwt_expiration`,
  `jwt_algorithm` and `jwt_extra_claims` only reached a backend whose class was named
  exactly `JWTAuthentication`. Subclasses get them too, unless they define their own
  `__init__`.
- **`LIGHTAPI_REDIS_URL` was read at import time**: the Redis client behind
  `Meta.cache` was built when `lightapi` was imported, so a URL set afterwards (in
  code, or by a test) was ignored. It is built on the first cache call now.
- **Redis failures are logged**: a cache read, write, invalidation or ping that fails
  still falls back to the database as before, but now leaves a warning with the
  traceback (`lightapi.cache`) instead of nothing. A `login_validator` that raises still
  answers `401`, and the exception is logged with its traceback (`lightapi._login`), as is
  a failed `CREATE TABLE` at `build_app()`.
- **The Redis client has a read timeout**: `socket_timeout=1` next to the existing
  `socket_connect_timeout=1`, so a Redis that accepts the connection and hangs costs one
  second and a cache miss, not a stuck worker.
- **Verb overrides and CRUD functions are resolved once, at `register()`**: a `get`/`post`
  method assigned to the endpoint class after `register()` is no longer picked up per
  request. Middleware classes are checked for `async def process` once per class.
- **`Pagination(style=...)` validates without rewriting the frozen field**; an invalid style
  raises `ConfigurationError` as before, and `Pagination.style` keeps the value as given
  (`PaginationStyle` member or its string).
- **`Authentication().build_backend()` without a backend raises `ConfigurationError`**
  instead of `AttributeError`; a CRUD call on an endpoint class that was never passed to
  `register()` raises `RuntimeError` naming the missing call instead of SQLAlchemy's
  `ArgumentError`.
- **Async apps create their tables in a Starlette lifespan** instead of the deprecated
  `on_startup` handler; same moment, no deprecation warning. `created_at`/`updated_at`
  column defaults no longer use the deprecated `datetime.utcnow()`; the stored value is the
  same naive UTC.
- **An async app on asyncpg no longer fails its first request after startup** ("Future
  attached to a different loop"). The startup created the tables on a worker thread with
  its own event loop, and the connection that did it went back to the pool bound to that
  loop. The lifespan now runs the DDL on the loop that serves the requests. `build_app()`
  called from inside an already running loop (a pytest-asyncio test) still uses the worker
  thread; create the tables yourself in that case.

## [Unreleased] — 0.1.24

### Fixed
- **`login_validator` exception → 401**: any exception raised by a `login_validator`
  now returns `401 Unauthorized` (same as returning `None`) instead of propagating
  as `500 Internal Server Error`. The exception is logged at `WARNING` level.
- **`SearchFilter` LIKE wildcard injection**: `%` and `_` in `?search=` values were
  treated as SQL LIKE wildcards, causing `hello_world` to match `helloXworld` and
  a bare `%` to match every row. Both characters are now escaped before the
  `ILIKE` pattern is applied.
- **`OrderingFilter` empty whitelist**: when `Meta.filtering.ordering` was not set,
  the guard `if allowed and …` short-circuited to allow ordering by any column.
  An empty or omitted whitelist now disables ordering entirely, consistent with how
  `FieldFilter` and `SearchFilter` handle unconfigured backends.
- **`PATCH null` clears `Optional` fields**: the `v is not None` guard in the PATCH
  update path prevented users from ever clearing a nullable column. The guard now
  consults the SQLAlchemy column inspector and allows `null` through for nullable
  columns; non-nullable columns still ignore `null` values.
- **`from_dict` fields were silently dropped**: `LightApi.from_dict()` stored field
  types as plain values without setting `__annotations__`, so `RestEndpointMeta`
  never created the corresponding columns. All user-defined fields were absent from
  every response. `__annotations__` is now populated before `type()` is called.
- **`from_dict` methods not enforced**: passing `methods=["GET", "POST"]` had no
  effect because `class_attrs["__bases__"]` is ignored by `type()`. `HttpMethod`
  mixins are now passed as real base-class arguments, so unlisted verbs correctly
  return `405 Method Not Allowed`.

### Changed
- `test_login_validator_exception_returns_500` updated to assert `401` and verify
  the `"Invalid credentials"` response body, reflecting the corrected behaviour.

### Documentation
- `README.md`: completed `LightApi()` constructor signature (added `mode`,
  `auth_path`, `session_manager`, `rate_limiter`, `login_validator`,
  `use_test_isolation`); corrected rate-limiter dict keys
  (`requests_per_minute` / `requests_per_hour` / `requests_per_day`); clarified
  that the rate limiter applies to `/auth/login` only; added notes on
  `SearchFilter` literal matching, `OrderingFilter` whitelist requirement, PATCH
  null-clearing for `Optional` fields, and `login_validator` exception handling.
- `docs/advanced/filtering.md`: added LIKE-literal paragraph and empty-whitelist
  behavior for `OrderingFilter`.
- `docs/api-reference/filters.md`: same additions in API-reference form.
- `docs/advanced/authentication.md`: documented that validator exceptions yield 401.
- `docs/api-reference/rest.md`: added `### PATCH and Optional fields` subsection.
- `docs/api-reference/core.md`: expanded `login_validator` description; noted that
  `from_dict` `methods` key enforces HTTP verbs.

---

## [0.1.23] — 2025-01-xx

### Fixed
- Docker image published under `iklob1/lightapi` instead of `iklobato/lightapi`.

---

## [0.1.22] — 2025-01-xx

### Added
- Published ready-to-use `iklob1/lightapi` Docker image with multi-arch support
  (`linux/amd64`, `linux/arm64`). Mount a YAML config and run without any Python
  install.

---

## [0.1.21] — 2025-01-xx

### Added
- 18 example scripts covering every LightAPI feature (`examples/01_minimal.py`
  through `examples/18_full_api.py`).
- `mode` parameter on `LightApi` for explicit sync/async selection (auto-detected
  from engine type and `async def` overrides when omitted).
- Global `rate_limiter` parameter on `LightApi`; configures the `/auth/login`
  rate-limiter via `RateLimiter` instance or `{"requests_per_minute": N, …}` dict.
- `validate_credentials` support on auth backends.
- `authentication/` submodule replacing the flat `auth.py` module.

### Fixed
- Async engine handling; `AsyncEngine` unwrapped correctly for sync callers.
- SQLAlchemy test-isolation pollution across test sessions.
- Auth-checker bugs with missing `Meta.authentication` configurations.

### Changed
- `_registry.py` service-locator pattern removed; session management is now
  injected directly via `SessionManager`.

---

## [0.1.20] — 2025-01-xx

### Changed
- Removed legacy v1 features and aligned documentation with v2 implementation.

---

## [0.1.19] — 2025-01-xx

### Changed
- Database connection now configured exclusively via `LIGHTAPI_DATABASE_URL`
  environment variable when no `engine` or `database_url` argument is passed.

---

## [0.1.18] — 2025-01-xx

### Changed
- Linter and type-checker configuration aligned; `ruff` and `mypy` clean across
  the core package.

---

## [0.1.17] — 2025-01-xx

### Fixed
- Test-suite failures in v2 integration tests resolved.

---

[Unreleased]: https://github.com/iklobato/lightapi/compare/v0.1.23...HEAD
[0.1.23]: https://github.com/iklobato/lightapi/compare/v0.1.22...v0.1.23
[0.1.22]: https://github.com/iklobato/lightapi/compare/v0.1.21...v0.1.22
[0.1.21]: https://github.com/iklobato/lightapi/compare/v0.1.20...v0.1.21
[0.1.20]: https://github.com/iklobato/lightapi/compare/v0.1.19...v0.1.20
[0.1.19]: https://github.com/iklobato/lightapi/compare/v0.1.18...v0.1.19
[0.1.18]: https://github.com/iklobato/lightapi/compare/v0.1.17...v0.1.18
[0.1.17]: https://github.com/iklobato/lightapi/compare/v0.1.16...v0.1.17
