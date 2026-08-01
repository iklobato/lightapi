# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions align with [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
