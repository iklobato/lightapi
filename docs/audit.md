# Audit of the OO refactor (branch `audit/second-pass`)

Single source of truth for the audit. Reference version: v0.1.29, commit `f6d727b` (the
last commit before any refactor; `d537385`, the branch base, differs from it by the version
bump only). Audited state: commit `804d716` (`refactor/oo-second-pass`, on top of PR #44,
#45 and #46).

## Summary (updated at every commit)

| Item | Occurrences | corrigido | justificado | proposta | aberto |
|---|---|---|---|---|---|
| P0 tests weakened | 0 | 0 | 0 | 0 | 0 |
| P0 HTTP differences | 0 | 0 | 0 | 0 | 0 |
| A1 loose functions | 2 | 0 | 2 | 0 | 0 |
| A2 closed-set literals | 1 | 1 | 0 | 0 | 0 |
| A3 own HTTPStatus | 0 | 0 | 0 | 0 | 0 |
| A4 dead code | 3 | 3 | 0 | 0 | 0 |
| A5 sync/async duplication | 2 | 0 | 2 | 0 | 0 |
| A6 stateless/utility classes | 3 | 0 | 3 | 0 | 0 |
| A7 duplicate flows | 1 | 0 | 1 | 0 | 0 |
| A8 backend construction | 1 | 0 | 1 | 0 | 0 |
| A9 per-request constants | 0 | 0 | 0 | 0 | 0 |
| A10 error replies | 3 | 2 | 1 | 0 | 0 |
| B1 silent errors | 18 | 5 | 11 | 2 | 0 |
| B2 hiding defaults | 12 | 5 | 7 | 0 | 0 |
| B3 sentinel returns | 3 | 0 | 3 | 0 | 0 |
| B4 lying types | 12 | 12 | 0 | 0 | 0 |
| B5 per-request checks | 9 | 3 | 6 | 0 | 0 |
| B6 silently disabled features | 5 | 1 | 0 | 4 | 0 |
| B7 blocking in async | 3 | 1 | 0 | 2 | 0 |
| B8 hidden mutation / globals | 5 | 1 | 4 | 0 | 0 |
| B9 dispatch by name | 5 | 3 | 2 | 0 | 0 |
| B10 time and formats | 3 | 2 | 1 | 0 | 0 |
| B11 weak security defaults | 6 | 1 | 3 | 2 | 0 |
| B12 resources and timeouts | 1 | 1 | 0 | 0 | 0 |
| B13 repeated work per request | 5 | 0 | 4 | 1 | 0 |
| B14 logs and warnings | 8 | 7 | 1 | 0 | 0 |
| B15 hidden YAGNI | 5 | 3 | 1 | 1 | 0 |
| B16 tests that do not protect | 5 | 2 | 3 | 0 | 0 |
| **Total** | **121** | **53** | **56** | **12** | **0** |

## Phase 0: baseline

Commands, run from each tree's root (`uv run --frozen --extra dev ...` for the current tree,
`uv run --directory ../lightapi-original --isolated --frozen --extra dev ...` for the
original worktree):

```
pytest tests/ -q -rxXs
pytest tests/ --cov=lightapi --cov-branch
ruff check lightapi
ruff format --check lightapi
mypy lightapi --strict --warn-unused-ignores
python -m build && twine check dist/*
```

| Measure | Original v0.1.29 (`f6d727b`) | Audit start (`804d716`) |
|---|---|---|
| pytest 3.10 | 327 passed, 1 xfailed, 2 xpassed, 544 warnings | 568 passed, 19 skipped, 1 xfailed, 2 xpassed, 715 warnings |
| pytest 3.13 (local `.venv`) | not run (SQLAlchemy 2.0.30 floor needs 3.10 to 3.12) | 568 passed, 19 skipped, 1 xfailed, 2 xpassed, 714 warnings |
| coverage `--cov-branch` (3.10) | 57% | 89% |
| ruff check / format | clean / 45 files | clean / 30 files |
| mypy `--strict --warn-unused-ignores`, project config | 3 errors (`auth_service.py`, a dead module) | 0 errors |
| same, with the per-module `ignore_errors` overrides removed | 190 errors in 29 files (18 modules ignored) | 60 errors in 12 files (16 modules ignored) |
| build + twine | PASSED | PASSED |
| `lightapi/` files / lines / classes / enums / loose functions | 45 / 7516 / 95 / 2 / 78 | 30 / 4675 / 81 / 10 / 6 |
| hidden-failure script: silent `except` / `getattr` with default | 37 / 82 | 20 / 22 |
| `ruff --select` appendix set (`--ignore TRY003`) | 404 findings | 206 findings |
| `vulture --min-confidence 80` | 0 | 0 |

The 19 skipped tests are `tests/integration/` (real Postgres/Redis, gated by env vars);
they did not exist in v0.1.29. The 2 XPASS exist in both versions.

### HTTP responses, original vs audit start

Same YAML (`/tmp/lightapi-audit/audit-{sync,async}.yaml`: `/books` full CRUD with an
optional int field, `/notes` GET only, `/secrets` JWT + IsAuthenticated, `/admin` JWT +
IsAdminUser, `auth.login_validator`, page_number pagination), same SQLite file, real uvicorn,
38 requests per run: `/healthz`, list empty, create, list, get, PUT, PATCH, PUT/PATCH stale
version (409), PUT without version (422), empty body (422), wrong type (422), invalid JSON
on POST and PUT, 404 on GET/PUT/DELETE, page 2, 405 (POST and PUT on a GET-only endpoint,
HEAD on a collection, GET on `/auth/login`), 401 (no token, bad token, bad login), 403
(user on an admin endpoint, GET and POST), login 422, DELETE 204, unknown route.

- sync, served by `lightapi serve`: 38/38 identical (status, `content-type`, `allow`,
  `www-authenticate`, body with timestamps and JWTs normalised).
- async: 38/38 identical. Served through a launcher that passes
  `engine=create_async_engine(url)` to `from_config`, because `lightapi serve` with
  `mode: async` in the YAML fails in BOTH versions (see B6-001).
- sync vs async within each version: 0 differences.

### Tests weakened against the original (`git diff f6d727b -- tests/`)

31 files changed, +3920 / -72 lines. No test file deleted, no test function removed (every
`def test_*` of v0.1.29 still exists under the same name), no file with fewer `assert`
statements, xfail markers 3 in both versions, skip markers 0 -> 7 (all new integration
tests). The 72 removed lines are renames of internal imports and patch targets
(`cache_helper.*`, `_resolve_name`, `normalise_serializer`, ...) and reformatting. Nothing
to restore.

## Tracking

Decisão: `corrigir`, `manter` (reason), `propor`. Status: `aberto`, `corrigido`,
`justificado`, `proposta`. Line numbers are those of commit `804d716`.

| ID | Item | Local | Problema | Decisão | Status | Commit |
|---|---|---|---|---|---|---|
| A1-001 | A1 | `lightapi/filters.py:56` | Module-level `_coerce_filter_value` | manter: `docs/api-reference/filters.md:130` teaches `from lightapi.filters import _coerce_filter_value`; pinned by `tests/test_public_api.py` | justificado | |
| A1-002 | A1 | `lightapi/cache.py:107` | Module-level `invalidate_cache_prefix` | manter: documented in `docs/advanced/caching.md:111`, patched by tests | justificado | |
| A2-001 | A2 | `lightapi/core.py:25` | `Response.__init__(status_code: int = 200)` literal default | corrigir: `HTTPStatus.OK` (same int, same signature) | corrigido | `d232ab8` |
| A4-001 | A4 | `lightapi/cache.py:76` | `RedisCacheBackend.delete` has no caller | corrigir: remove | corrigido | `bfe14c4` |
| A4-002 | A4 | `lightapi/config.py:40` | `LIGHTAPI_JWT_ALGORITHM` env fallback is unreachable: `jwt_algorithm` defaults to `"HS256"` (truthy), so `self.jwt_algorithm or environ.get(...)` never reads the env; same in v0.1.29; undocumented | corrigir: drop the dead env read | corrigido | `57dbb6d` |
| A4-003 | A4 | `lightapi/rest.py:185` | `cls.__dict__.get("queryset")` before `getattr(cls, "queryset", None)`: the first lookup is covered by the second | corrigir: one `getattr` | corrigido | `8b07b00` |
| A5-001 | A5 | `lightapi/cache.py:116` | `EndpointCache.serve` and `serve_async` repeat check/hit/call/store, differing only by the threadpool hop around Redis | manter: the prompt forbids a generic sync/async executor; only the I/O hop differs | justificado | |
| A5-002 | A5 | `lightapi/lightapi.py:284` | `_create_tables` (sync `create_all`) and `_create_tables_inside_running_loop` (own loop on a thread) | manter: different mechanisms, no shared logic | justificado | |
| A6-001 | A6 | `lightapi/session_manager.py:72` | `SessionManager` carries the "Manager" name | manter: holds engine, metadata and registry (state), public constructor kwarg `session_manager=` documented in README | justificado | |
| A6-002 | A6 | `lightapi/schema.py:100` | `SchemaFactory` is a class of static methods | manter: in `lightapi.__all__`; `build_from_reflected_table` documented and tested by name | justificado | |
| A6-003 | A6 | `lightapi/repository.py:23` | `VersionedRow` Protocol | manter: a structural type for every mapped class, used for typing only, not dispatch | justificado | |
| A7-001 | A7 | `lightapi/_dict_config_loader.py:38` | `DictConfig.build` and `LightAPIConfig.build_app` both build an app from a config | manter: two public input formats (`from_dict` is deprecated and goes in 0.2.0) | justificado | |
| A8-001 | A8 | `lightapi/lightapi.py:174` | `_login_backend` picks the login backend with `issubclass(backend, kind)` over (JWT, Basic) | manter: single construction point stays `Authentication.build_backend`; this chooses which endpoint's backend answers `/auth/login`, by class, not by name | justificado | |
| A10-003 | A10 | `lightapi/endpoint_handler.py:102` | `EndpointGuard.check` answered every failed authentication with the generic `{"detail": "Authentication required"}` + `WWW-Authenticate: Bearer`; the backend's `get_auth_error_response()` (the documented hook; JWT's text is the one the README lists; Basic's carries the `Basic realm` challenge) never ran on the guard path. Same in v0.1.29. Found by e2e scenario 04 | corrigido: the guard returns `backend.get_auth_error_response(request)`; `ApiError.AUTHENTICATION_REQUIRED` removed | corrigido | `338e450` |
| A10-002 | A10 | `lightapi/lightapi.py:146`, `endpoint_handler.py:224` | The routes listed only the allowed methods, so Starlette answered every other verb with its text/plain 405; the JSON 405 the README documents (`{"detail": "Method Not Allowed. Allowed: GET"}`) was reachable only by HEAD. Found by e2e scenario 03 | corrigido: every CRUD verb reaches the handler, which binds only the allowed ones and answers the JSON 405 with `Allow` for the rest; same on `/auth/login` | corrigido | `6ad5247` |
| A10-001 | A10 | `lightapi/endpoint_handler.py:299`, `rate_limiter.py:165`, `core.py:157`, `authentication/basic.py:69` | Error replies built outside `ApiError`: dynamic 405 (`Allow` lists the route's verbs), 429 (public `get_rate_limit_response`), compat 403 `{"error": "not allowed"}`, Basic 401 `{"error": ...}` (public method, no internal caller); JWT/Base 401 are FROZEN | manter: each shape is a public method or a documented body | justificado | |
| B1-001 | B1 | `lightapi/_dict_config_loader.py:89` | Unknown `auth:` value in a dict config is ignored (no backend); v0.1.29 did the same with `if auth == "jwt" ... elif "basic"` | propor: `ConfigurationError` at `from_dict` (visible: an app that built now fails); alternative: keep, the path is deprecated | proposta | |
| B1-002 | B1 | `lightapi/_login.py:49` | Login body that is not JSON/UTF-8 becomes `{}` and a 422 "Field required" | manter: specific exceptions; the 422 body is contract (pinned) | justificado | |
| B1-003 | B1 | `lightapi/_login.py:61` | Malformed `Authorization: Basic` returns None, then 401 | manter: client error mapped to one reply; specific exceptions | justificado | |
| B1-004 | B1 | `lightapi/_login.py:121` | `except Exception` around the user's `login_validator` returns None (401) and logs without the traceback | manter the except (documented since 0.1.24: any exception is a 401); corrigir the log: `exc_info=True`, `# noqa: BLE001` with the reason | corrigido | `f08edc2` |
| B1-005 | B1 | `lightapi/cache.py:50,61,71,81,93,102` | `RedisCacheBackend` turns every `redis.RedisError` (and a bad cached payload) into None/False silently | corrigir: keep the fallback, log `warning(..., exc_info=True)` (prompt rule for optional dependencies) | corrigido | `4171583` |
| B1-006 | B1 | `lightapi/constants.py:63` | `HttpVerb.of` returns None for a method outside the enum (HEAD) | manter: expected absence, answered with 405 | justificado | |
| B1-007 | B1 | `lightapi/endpoint_handler.py:296` | Malformed JSON body becomes `{}` and a 422 "Field required" (`json.JSONDecodeError`, `UnicodeDecodeError` only) | manter: specific exceptions, 422 body is contract. A 422 saying "invalid JSON" would be a visible change | justificado | |
| B1-008 | B1 | `lightapi/filters.py:52` | A filter value the column type cannot parse (`?price=abc`) is passed through as the string: no rows on SQLite, a DB error (500) on Postgres; same in v0.1.29. e2e scenario 06 on Postgres hit the 500 | corrigido: `_coerce_filter_value` raises `FilterValueError`, `_list` answers 422 with `loc: ["query", param]` | corrigido | `64a38f3` |
| B1-009 | B1 | `lightapi/lightapi.py:311` | `except RuntimeError: return` when no loop runs | manter: `asyncio.get_running_loop()` signals absence by raising; the return defers to the startup handler | justificado | |
| B1-010 | B1 | `lightapi/lightapi.py:303` | A failed `create_all` at `build_app` is logged as a warning without traceback and the app serves 500s; same in v0.1.29 (`except Exception`) | corrigir the log (`exc_info=True`); the fail-fast is B1-011 | corrigido | `d21960f` |
| B1-011 | B1 | `lightapi/lightapi.py:303` | Same site: should `build_app` raise instead of warn? | propor: raise `ConfigurationError` from the DDL error (visible: startup fails instead of every request); alternative: keep the warning | proposta | |
| B1-012 | B1 | `lightapi/pagination.py:129` | `?page=abc` becomes page 1 | manter: PR #46 behavior, pinned by `tests/test_second_pass_characterization.py` | justificado | |
| B1-013 | B1 | `lightapi/pagination.py:184` | An invalid cursor is ignored (first page) | manter: v0.1.29 behavior, pinned by a test; 422 would be visible | justificado | |
| B1-014 | B1 | `lightapi/schema.py:157` | `NotImplementedError` from `column.type.python_type` becomes None, then `Any` with a logged warning | manter: SQLAlchemy raises it for types without a Python type; the fallback is logged | justificado | |
| B1-015 | B1 | `lightapi/table_mapping.py:126` | `get_type_hints` failure falls back to raw annotations | manter: ends in `ConfigurationError("... not in the type map")` with the field name | justificado | |
| B1-016 | B1 | `lightapi/yaml_config.py:531` | `except ValueError: return fn` for a callable without an inspectable signature | manter: builtins; the validator is still called with two args | justificado | |
| B1-017 | B1 | `lightapi/authentication/jwt.py:84`, `lightapi/cache.py:243,262` | Silent excepts inside FROZEN classes | manter: FROZEN | justificado | |
| B1-018 | B1 | `lightapi/cache.py:49` | `redis.from_url` failure (bad URL) returns no client, silently, forever | corrigir with B1-005 (log once per call) | corrigido | `4171583` |
| B2-001 | B2 | `lightapi/filters.py:71,97,125` | `getattr(view, "_meta", {})` on a view that is always a `RestEndpoint` (has `_meta`) | corrigir: `view._meta.get("filtering")` | corrigido | `5e91407` |
| B2-002 | B2 | `lightapi/lightapi.py:324` | `getattr(cls, "_meta", {})` on a registered endpoint (validated by `_require_rest_endpoint`) | corrigir: `cls._meta` | corrigido | `5e91407` |
| B2-003 | B2 | `lightapi/rest.py:171` | `getattr(type(self), "_session_manager", None)` | corrigir: declare `_session_manager: ClassVar[SessionManager | corrigido | `5e91407` | |
| B2-004 | B2 | `lightapi/authentication/base.py:118,125` | `getattr(request.state, "user", None)` | manter: Starlette `State` raises for a missing attribute; absent means unauthenticated | justificado | |
| B2-005 | B2 | `lightapi/rest.py:78,79,105,116-121,130,187` | `getattr(Meta, ...)`, `getattr(base, "_http_method")`, `getattr(cls, "queryset")` | manter: `Meta` attributes and hooks are optional by design | justificado | |
| B2-006 | B2 | `lightapi/schema.py:213`, `lightapi/table_mapping.py:133` | `getattr(base, "__annotations__", {})` | manter: on 3.10 a class without annotations has no `__annotations__` | justificado | |
| B2-007 | B2 | `lightapi/pagination.py:187,194` | `getattr(qs, "columns_clause_froms", ())`, `getattr(row, "id", None)` | manter: the queryset and its rows come from the user's `queryset` hook | justificado | |
| B2-008 | B2 | `lightapi/filters.py:41,45` | `hasattr(col, "property")`, `getattr(col, "type", None)` | manter: SQLAlchemy exposes the type on `InstrumentedAttribute` and `Column` differently | justificado | |
| B2-009 | B2 | `lightapi/cache.py:31` | `LIGHTAPI_REDIS_URL` defaults to `redis://localhost:6379/0` | manter: documented default, same in v0.1.29 | justificado | |
| B2-012 | B2 | `lightapi/yaml_config.py` (every block model) | The YAML models used pydantic's default `extra="ignore"`: a key the format does not know (`defaults.filtering`, `meta.paginate`, a misspelt top-level key) was dropped and the app started without the feature, while `docs/getting-started/configuration.md:89` promises a typo fails at load time. Same in v0.1.29. Found by e2e scenario 12 | corrigido: every block model inherits `_Document` with `extra="forbid"`; `FieldSpec` keeps `extra="allow"` for the constraint keys | corrigido | `see git log: fix(B2-012)` |
| B2-011 | B2 | `lightapi/schema.py:254`, `table_mapping.py:228` | A reflected table required every non-auto column on POST, nullable or not, and on `reflect = "partial"` the declared `Field()` (default, constraints) was stripped before the schema was built, so `notes: str = Field(default="")` still answered 422 "Field required". Same in v0.1.29. Found by e2e scenario 11 | corrigido: nullable reflected columns are optional (None); `ReflectedTable.map` keeps the declared FieldInfos and `build_from_reflected_table(cls, table, declared)` uses them | corrigido | `0adf7b1` |
| B2-010 | B2 | `lightapi/rest.py:197,202,217`, `endpoint_handler.py:192`, `table_mapping.py:65`, `lightapi.py:170,324` | `_meta.get("pagination")` etc. on keys `_parsed_meta` always writes | manter: `_meta` is `{}` for `base_only` classes | justificado | |
| B3-001 | B3 | `lightapi/cache.py:57-105` | `RedisCacheBackend` methods return None/False on failure | manter: "no Redis, no cache, requests still answered" is the documented contract; B1-005 adds the log | justificado | |
| B3-002 | B3 | `lightapi/_login.py:42,56,108` | `from_request`, `parse_basic_header`, `_validated_user` return None | manter: each None maps to exactly one reply (401/422) | justificado | |
| B3-003 | B3 | `lightapi/constants.py:63,87`, `config.py:64`, `yaml_config.py:375`, `table_mapping.py:140` | `HttpVerb.of`, `TableReflection.from_meta`, `permission_for`, `field_info`, `_column_for` return None | manter: None means "not configured / not applicable", not failure | justificado | |
| B4-001 | B4 | `lightapi/fields.py:9,18,25`, `lightapi/schema.py:135,235,253,255` | 7 `# type: ignore` comments that mypy reports as unused once the module is checked | corrigir: remove | corrigido | `639dd6d` |
| B4-002 | B4 | `lightapi/config.py:92-95` | `Filtering` fields typed `tuple[...]`; YAML and dict loaders pass `list` or `None` (`yaml_config.py:187-190`, `_dict_config_loader.py:106`) | corrigir: `Sequence[...] | corrigido | `b6cfdff` | |
| B4-003 | B4 | `lightapi/config.py:59` | `Authentication.jwt_extra_claims: tuple[str, ...]` receives `list \| None` from YAML (`yaml_config.py:162`) | corrigir: `Sequence[str] \| None` | corrigido | `b6cfdff` |
| B4-004 | B4 | `lightapi/config.py:104` | `Pagination.style: PaginationStyle` but a `str` is accepted and rewritten in `__post_init__` (B8-001) | corrigir: `PaginationStyle | corrigido | `07b83af` | |
| B4-005 | B4 | `lightapi/config.py:56,58` | `Authentication.backend: type \| None`, `permission: type \| dict[str, type] \| None` | corrigir: `type[BaseAuthentication]`, `type[BasePermission]`; `build_backend()` on a None backend raises `ConfigurationError` | corrigido | `b6cfdff` |
| B4-006 | B4 | `lightapi/lightapi.py:100,91` | `register(mapping: dict[str, type])`, `_endpoint_map: dict[str, type]` | corrigir: `type[RestEndpoint]` (same signature) | corrigido | `be91dd1` |
| B4-007 | B4 | `lightapi/config.py:92` | `Filtering.backends: tuple[type, ...]` | corrigir: `Sequence[type[BaseFilter]] | corrigido | `b6cfdff` | |
| B4-008 | B4 | `lightapi/core.py:26` | `Response(headers: Dict \| None)` | corrigir: `dict[str, str] \| None` | corrigido | `024d1c1` |
| B4-009 | B4 | 89 `Any` annotations (ANN401), by file: filters 16, rest 13, core 10, yaml_config 8, pagination 8, lightapi 7, table_mapping 6, others 21 | `Any` where a real type exists (`Request`, `Response | corrigido: `Select[Any]`, `Engine`/`AsyncEngine`, `Request`/`Response | None`, `VersionedRow`, `type[BasePermission]`, `FieldInfo | None`, `Column`/`Table`/`Connection`, `object`; the `Any` that stay (forwarded kwargs, JSON values, the engine whose kind is a runtime fact) carry `# noqa: ANN401` with the reason | corrigido | `c3465a4` | |
| B4-010 | B4 | `pyproject.toml:159-176` | `ignore_errors = true` for 16 modules hides 60 strict errors (v0.1.29: 18 modules, 190 errors) | corrigir: remove the modules that reach zero after B4-001..008 and B4-011; manter the rest with the reason in the TOML (`cache.py`: redis stubs; `fields.py`: pydantic `Field` overloads) | corrigido | `97a8e0b` |
| B4-011 | B4 | `lightapi/rest.py:81-92` | 7 `# type: ignore[attr-defined]` because `_process(cls: type)` sets attributes only `RestEndpoint` declares | corrigir: `cls: type[RestEndpoint]`, declare `__schema_create__`/`__schema_read__`/`_session_manager` on `RestEndpoint` | corrigido | `179c67f` |
| B4-012 | B4 | `lightapi/yaml_config.py:325` | `assert isinstance(self.methods, dict)` as type narrowing (also S101) | corrigir: pass the dict to the method | corrigido | `f8bf3c4` |
| B5-001 | B5 | `lightapi/endpoint_handler.py:254-265,276` | Per request: `getattr(cls, verb.override)` + `inspect.isfunction`, `asyncio.iscoroutinefunction(override)`, `getattr(endpoint, verb.sync_name/async_name)` | corrigir: resolve the override (and whether it is async) and the built-in CRUD function once per route in `EndpointHandler.__init__` | corrigido | `1f7edd4` |
| B5-002 | B5 | `lightapi/endpoint_handler.py:57` | `asyncio.iscoroutinefunction(middleware.process)` per middleware, twice per request | corrigir: decide once per class in `MiddlewareChain` | corrigido | `5148ac8` |
| B5-003 | B5 | `lightapi/session_manager.py:49,55,61` | `hasattr(self._local, ...)` lazy init of thread-local state | corrigir: a `threading.local` subclass whose `__init__` builds the state | corrigido | `8d19606` |
| B5-004 | B5 | `lightapi/rest.py:190` | `callable(qs_attr)` per request | manter: the `queryset` hook may be a `Select` or a function; one call | justificado | |
| B5-005 | B5 | `lightapi/rest.py:328` | `inspect.isawaitable(qs)` per async request | manter: an `async def queryset` only yields a coroutine when called | justificado | |
| B5-006 | B5 | `lightapi/schema.py:113-122` | `isinstance`/`hasattr` per row in `row_to_dict` | manter: the row shape depends on the user's queryset (entity, Row, dict) | justificado | |
| B5-007 | B5 | `lightapi/session_manager.py:90` | `hasattr(engine, "sync_engine")` | manter: once at construction; `AsyncEngine` lives in the optional `async` extra | justificado | |
| B5-008 | B5 | `lightapi/endpoint_handler.py:240` | `isinstance(result, dict)` per request | manter: an override may return a dict (documented) | justificado | |
| B5-009 | B5 | `lightapi/filters.py:41-50` | `hasattr`/`isinstance` on the column type per filter parameter | manter: SQLAlchemy type dispatch, one parameter at a time | justificado | |
| B6-001 | B6 | `lightapi/yaml_config.py:465`, `lightapi.py:115` | YAML `mode: async` with `database.url` can never start: `from_config` builds a sync `Engine`, then `register()` raises `mode='async' requires AsyncEngine, got Engine`. `lightapi serve` cannot serve an async app. Same in v0.1.29 | corrigido: `_engine_from_url(url, mode)` builds an `AsyncEngine` in async mode; a URL without an async driver is a `ConfigurationError` naming the drivers. e2e scenario 12 serves the async document | corrigido | `4248fc8` |
| B6-002 | B6 | `lightapi/config.py:125`, `cache.py:166` | `Cache.vary_on` is documented (`docs/advanced/caching.md:57-141`: "only the listed query parameters contribute to the key") but never read; the key is always the full query string. Same in v0.1.29 | propor: implement (visible: cache keys and hits change for apps that set it) or fix the docs | proposta | |
| B6-003 | B6 | `lightapi/config.py:31` | `Config.jwt_expiration` is never read: `JWTAuthentication.generate_token` (FROZEN) uses `self.expiration or 3600` | propor: remove the field in 0.2.0 or make the FROZEN class read it | proposta | |
| B6-004 | B6 | `lightapi/lightapi.py:291` | `LightApi(engine=AsyncEngine)` without `mode="async"` and without an `async def` hook: tables are never created and every request is a 500 (now with a startup warning; v0.1.29 swallowed an `AttributeError`) | propor: detect async mode from the engine type (visible: 500s become a working app); alternative: `ConfigurationError` at register | proposta | |
| B6-005 | B6 | `lightapi/authentication/basic.py:61` | An `async def validate_credentials` on a `BasicAuthentication` subclass: `authenticate` does not await it, the coroutine is truthy, so any Basic credentials pass and `request.state.user` is a coroutine (same in v0.1.29; `LoginEndpoint` does await it). Security relevant (B11) | propor: `ConfigurationError` at startup for an async validator on Basic, or await it in the guard | proposta | |
| B7-001 | B7 | `lightapi/endpoint_handler.py:92` | `EndpointGuard.check` runs `backend.authenticate` on the event loop; a Basic validator that queries a database blocks the loop | propor: run sync backends through `run_blocking` (invisible when the validator is thread-safe; breaks validators bound to a `StaticPool` SQLite) | proposta | |
| B7-002 | B7 | `lightapi/_login.py:116` | A sync `login_validator` runs on the event loop | propor: same as B7-001 | proposta | |
| B7-003 | B7 | `lightapi/lightapi.py:308-318`, `table_mapping.py:237-249` | `asyncio.run` on a worker thread while a loop is running (bug B19, both versions); e2e scenario 02 on asyncpg failed its first POST with "Future attached to a different loop" | corrigido for a served app: the lifespan awaits `create_all` on the serving loop; `build_app()` inside an already running loop (pytest-asyncio) and async reflection keep the worker thread, documented in the CHANGELOG | corrigido | `1758f90` |
| B8-001 | B8 | `lightapi/config.py:116` | `object.__setattr__` on the frozen `Pagination` | corrigir with B4-004: no mutation | corrigido | `07b83af` |
| B8-002 | B8 | `lightapi/config.py:54` | Module global `config = Config()`, read per request by the FROZEN `JWTAuthentication` | manter: documented as `lightapi.config.config` | justificado | |
| B8-003 | B8 | `lightapi/session_manager.py:66` | Module global `_state` (metadata + registry) | manter: SQLAlchemy needs one registry per process; `reset()` is the documented hook for tests | justificado | |
| B8-004 | B8 | `lightapi/cache.py:34` | `RedisCacheBackend.shared()` process-wide client | manter: one client per process, built on first use (so `LIGHTAPI_REDIS_URL` set after import counts) | justificado | |
| B8-005 | B8 | `lightapi/rest.py:66-92`, `lightapi.py:124`, `table_mapping.py:72-78` | The metaclass and `register()` write `_meta`, `_allowed_methods`, schemas, `_session_manager` on the user's class; `_strip_field_infos` deletes class attributes | manter: that is the registration protocol; every attribute is documented in README "RestEndpoint internals" | justificado | |
| B9-001 | B9 | `lightapi/rest.py:63` | `if name == "RestEndpoint"` skips the root class by name | corrigir: `if not bases` (the root class has no bases) | corrigido | `5e91407` |
| B9-002 | B9 | `lightapi/constants.py:72` | `getattr(HttpMethod, verb.value)` builds the verb-to-mixin map | corrigir: an explicit dict | corrigido | `139303e` |
| B9-003 | B9 | `lightapi/endpoint_handler.py:260,265` | `getattr(endpoint, verb.async_name)` / `sync_name` string dispatch per request | corrigir with B5-001 | corrigido | `1f7edd4` |
| B9-004 | B9 | `lightapi/yaml_config.py:495,514` | `importlib.import_module` for dotted names | manter: the YAML border; dotted paths are the documented way to name custom classes | justificado | |
| B9-005 | B9 | `lightapi/lightapi.py:394,404` | `importlib.import_module` probing `sqlalchemy.ext.asyncio` and the async driver | manter: optional-dependency check at startup with an install hint | justificado | |
| B10-001 | B10 | `lightapi/table_mapping.py:186-191` | `datetime.datetime.utcnow` as column defaults (deprecated since 3.12; `Repository` always passes the timestamps, so only inserts made outside LightAPI hit them) | corrigir: the same naive UTC value from a non-deprecated call | corrigido | `ca70112` |
| B10-002 | B10 | `lightapi/repository.py:55` | Timestamps stored and returned as naive UTC (`.replace(tzinfo=None)`) | manter: the stored format is contract (`CREATE TABLE` identical to v0.1.29); aware timestamps would be a visible change | justificado | |
| B10-003 | B10 | `lightapi/yaml_config.py:448` | `open(config_path)` | corrigir: `Path(config_path).open()` | corrigido | `3988875` |
| B11-001 | B11 | `lightapi/lightapi.py:213-218` | With `cors_origins` set: `allow_methods=["*"]`, `allow_headers=["*"]`, `allow_credentials=True` (same in v0.1.29) | propor: credentials off by default, or a documented opt-in; visible for browser clients | proposta | |
| B11-002 | B11 | `lightapi/core.py:98` | Compat `CORSMiddleware` defaults `allow_origins=["*"]` | propor: same as B11-001 (public compat class, documented default) | proposta | |
| B11-003 | B11 | `lightapi/yaml_config.py:325` | `assert` as validation | corrigir with B4-012 | corrigido | `f8bf3c4` |
| B11-004 | B11 | `lightapi/constants.py:37` | `ResponseKey.TOKEN = "token"` flagged S105 | manter: a JSON key, not a secret (`# noqa: S105`) | justificado | |
| B11-005 | B11 | `lightapi/lightapi.py:185`, `server.py:27`, `rate_limiter.py:124` | `0.0.0.0` (S104) | manter: documented defaults of `run()` and `lightapi serve`; the limiter's fallback IP when the client is unknown (`# noqa: S104`) | justificado | |
| B11-006 | B11 | `lightapi/constants.py:107` | 422 replies echo pydantic's error list including `input` | manter: the 422 body shape is contract (pinned by tests and the differential harness) | justificado | |
| B12-001 | B12 | `lightapi/cache.py:49` | `redis.from_url(..., socket_connect_timeout=1)` without `socket_timeout`: a Redis that accepts the connection and hangs blocks a worker thread for every cached request | corrigir: `socket_timeout` equal to the existing connect timeout (the only measured datum in the code base) | corrigido | `868034d` |
| B13-001 | B13 | `lightapi/repository.py:57` | `nullable_columns` runs `class_mapper(...)` on every PUT/PATCH | manter: a `functools.cache` keyed on the model class pinned every endpoint class and its engine for the life of the process (aiosqlite worker threads then kept pytest from exiting); one `class_mapper` call per PUT/PATCH stays, with the reason in a comment | justificado | `3d43b7b` |
| B13-002 | B13 | `lightapi/rest.py:198` | A filter backend instance is created per request | propor: instantiate once per `Filtering`; visible for a user backend that keeps per-request state on `self` (would then be shared across threads) | proposta | |
| B13-003 | B13 | `lightapi/cache.py:164` | `json.loads(response.body)` re-parses the body the CRUD just serialized, on every cached GET miss | manter: the public CRUD methods return `Response` objects; keeping the dict would change their contract | justificado | |
| B13-004 | B13 | `lightapi/endpoint_handler.py:42,50` | Middleware classes are instantiated per request (twice) | manter: v0.1.x contract; `Middleware` subclasses with `__init__` state rely on it | justificado | |
| B13-005 | B13 | `lightapi/endpoint_handler.py:233` | `HttpVerb.of(request.method)` (try/except) per request | manter: one enum lookup | justificado | |
| B14-001 | B14 | `lightapi/lightapi.py:126-127` | `logger.info(f"...")`, `logger.debug(f"...")` (G004) | corrigir: `%s` arguments | corrigido | `adfcd85` |
| B14-002 | B14 | `lightapi/lightapi.py:304` | `logger.warning("Table creation warning: %s", exc)` without `exc_info` | corrigir: `exc_info=True` (B1-010) | corrigido | `d21960f` |
| B14-003 | B14 | `lightapi/_login.py:122` | `logger.warning("validate_credentials raised: %s", exc)` without `exc_info` | corrigir: `exc_info=True` (B1-004) | corrigido | `f08edc2` |
| B14-004 | B14 | `lightapi/lightapi.py:211` | Test warning: Starlette `on_startup` is deprecated | corrigir: `lifespan` | corrigido | `63bcd5c` |
| B14-005 | B14 | `lightapi/table_mapping.py:108` | Test warning: `Column.copy()` is deprecated (SQLAlchemy 1.4); the copy dates from when columns were shared across re-registrations, `from_endpoint` now builds fresh columns per class | corrigir: drop the copy (verify with the e2e and isolation tests) | corrigido | `daf38fb` |
| B14-006 | B14 | `pytest.ini:4` | Test warning: `PytestConfigWarning: Unknown config option: env` (pytest-env is not installed; the values were never applied). `pytest.ini` also shadows `[tool.pytest.ini_options]` in `pyproject.toml`, so `xfail_strict` must go where pytest reads it | corrigir: move `asyncio_mode` and `markers` to `pyproject.toml`, delete `pytest.ini`, add `xfail_strict = true` | corrigido | `d1ee2a8` |
| B14-007 | B14 | 11 test modules (e.g. `tests/test_async_crud.py` and `tests/test_second_pass_characterization.py` both define `Widget`) | 13 `SAWarning: This declarative base already contains a class with the same class name and module name` | corrigir in tests: unique class names per module | corrigido | `56a7ebd` |
| B14-008 | B14 | `lightapi/lightapi.py:325` | `warnings.warn(RuntimeWarning)` when Redis is unreachable at startup | manter: a user-facing startup warning, pinned by `tests/test_cache_v2.py` | justificado | |
| B15-001 | B15 | 27 ARG002/ARG003 sites (`retrieve(request, pk)`, `destroy(request, pk)`, `_retrieve_async`, `_destroy_async`, base-class `authenticate`/`has_permission`/`validate_credentials`/`from_config`, `get_rate_limit_response(request)`, `HealthCheckEndpoint`, `BaseCache` FROZEN, `Middleware.process`) | Unused parameters | manter: every one is a public signature (pinned by `tests/data/public_api.json`) or an interface method; each carries `# noqa: ARG002`/`ARG003` with the reason; `BaseCache` (FROZEN) is exempted at module level in `cache.py` | justificado | `c3465a4` |
| B15-002 | B15 | `lightapi/config.py:60`, `authentication/jwt.py:37`, `basic.py:30` | `Authentication.rate_limiter` is stored on the backend and never read | propor: remove in 0.2.0 (public field) | proposta | |
| B15-003 | B15 | `lightapi/__init__.py:60`, `lightapi/rate_limiter.py:52` | ERA001: section labels inside `__all__` and a structure comment read as commented-out code | corrigir: sort `__all__` without labels (RUF022), reword the comment | corrigido | `efd6160` |
| B15-004 | B15 | `lightapi/__init__.py:30` | `# noqa: E402` no longer needed (RUF100) | corrigir: remove | corrigido | `efd6160` |
| B15-005 | B15 | `lightapi/rest.py:244,270`, `yaml_config.py:246` | Internal methods with a positional boolean (`_update(..., partial)`, `_update_values(..., partial, ...)`, `build_meta_class(..., reflect)`) | corrigir: keyword-only; the public `update(data, pk, partial=False)` stays | corrigido | `841ff4a` |
| B16-001 | B16 | `tests/test_filtering.py:223`, `tests/test_rest.py:204` | `xfail` markers on tests that pass (XPASS in both versions) | corrigir: remove the markers, enable `xfail_strict` | corrigido | `c5a387f` |
| B16-002 | B16 | `tests/test_cache_v2.py:144` | `if len(keys) >= 2: assert ...` can pass without asserting | corrigir: assert the count, then the keys | corrigido | `a7f3086` |
| B16-003 | B16 | `tests/test_serializer.py:96-97`, `tests/test_pipeline.py:97-126` | Tests read `_meta["serializer_normalised"]` | manter: `_meta` is documented as the parsed `Meta` dict (README); the tests pin the projection a declared `Meta` yields | justificado | |
| B16-004 | B16 | `tests/test_cache_v2.py`, `tests/test_cache_async.py` | Tests patch `RedisCacheBackend.get/set/invalidate_prefix/ping` (own code) | manter: it is the Redis boundary wrapper; a real Redis is covered by `tests/integration/test_redis_cache.py` | justificado | |
| B16-005 | B16 | `tests/integration/` | 19 tests skipped without `LIGHTAPI_TEST_PG_*` / `LIGHTAPI_REDIS_URL` | manter: need real services; the skip reason names the variable | justificado | |

## Phase 3: verification (audit end, commit `83d12a2`)

Same commands as Phase 0. Python 3.10 through `uv run --isolated --frozen --python 3.10
--extra dev`, Python 3.13 through the local `.venv`.

| Measure | Original v0.1.29 (`f6d727b`) | Audit start (`804d716`) | Audit end (`83d12a2`) |
|---|---|---|---|
| pytest 3.10 | 327 passed, 1 xfailed, 2 xpassed, 544 warnings | 568 passed, 19 skipped, 1 xfailed, 2 xpassed, 715 warnings | 589 passed, 19 skipped, 1 xfailed, 0 warnings |
| pytest 3.13 | not run | 568 passed, 19 skipped, 1 xfailed, 2 xpassed, 714 warnings | 589 passed, 19 skipped, 1 xfailed, 0 warnings |
| coverage `--cov-branch` (3.10) | 57% | 89% | 90% |
| ruff check, project config | clean (`E,F,W,I`) | clean (`E,F,W,I`) | clean (the appendix set, see below) |
| `ruff --select` appendix set (`--ignore TRY003`) on `lightapi/` | 404 findings | 206 findings | 0 |
| same set on `tests/` and `examples/` with the per-file ignores below | not measured | 187 findings | 0 |
| ruff format | 45 files clean | 30 files clean | 106 files clean (`lightapi`, `tests`, `examples`) |
| mypy, project config | 3 errors (dead `auth_service.py`) | 0 | 0 |
| mypy `--strict --warn-unused-ignores`, no `ignore_errors` overrides | 190 errors in 29 files (18 modules ignored) | 60 in 12 files (16 modules ignored) | 5 in 1 file (1 module ignored: `lightapi.cache`, redis-py stubs) |
| `[tool.mypy]` modules with `ignore_errors` | 18 | 16 | 1 |
| build + twine | PASSED | PASSED | PASSED |
| `mkdocs build --strict` | not measured | not measured | passes |
| `lightapi/` files / lines / classes / enums / loose functions | 45 / 7516 / 95 / 2 / 78 | 30 / 4675 / 81 / 10 / 6 | 30 / 4943 / 84 / 10 / 6 |
| radon raw: LOC / LLOC / SLOC / comment lines | 7516 / 4037 / 5024 / 294 | 4675 / 2642 / 3127 / 166 | 4943 / 2730 / 3336 / 242 |
| hidden-failure script: silent `except` / `getattr` with default | 37 / 82 | 20 / 22 | 1 / 2 |
| `vulture --min-confidence 80` | 0 | 0 | 0 |
| xfail / xpass | 1 / 2 | 1 / 2 | 1 / 0, with `xfail_strict = true` |
| pytest warnings of any kind | 544 | 715 | 0, with `filterwarnings = ["error", ...]` |

The three hidden-failure sites that remain are the documented fallbacks of
`DeclaredTable._field_annotations` (`get_type_hints` on a string annotation that cannot be
evaluated) and the two `getattr(base, "__annotations__", {})` over an MRO that includes
`object`.

### HTTP responses, original vs audit end

Same procedure as Phase 0 (`/tmp/lightapi-audit/final-{sync,async}.json` against
`orig-{sync,async}.json`): 38/38 identical in sync, 38/38 identical in async. The only byte
that differs is the port inside the `previous` pagination URL of step `list-page-2`, which
is the port each run was served on.

### Tests weakened

None. No test deleted, skipped or loosened. Changes to existing tests, all in their own
commits: `B14-007` (unique class names per module; fixture-built endpoint classes moved to
module scope; async fixtures dispose their engines), `B16-001` (two `xfail` markers removed
from tests that pass), `B16-002` (the vary_on test asserts its two writes), and the lint
conformance edits of `83d12a2` (combined `with` blocks, `Path.unlink`, `ClassVar` on test
doubles, `yaml.YAMLError` instead of `Exception`, raw regex strings, `# noqa` with a reason
on the subprocess, urlopen and forced-exception lines). `tests/test_audit.py` adds 21 tests,
one per fixed ID, in the commit that fixes the ID.

### Where the result departs from the brief

- **Lines of `lightapi/` grew**: 4675 -> 4943 physical lines (+268, +5.7%), 2642 -> 2730
  logical lines (+88). Of the physical growth, +76 are comment lines (the `# noqa` reasons
  and the comments the brief asks for on every justified line) and most of the rest is
  ruff format wrapping a signature onto several lines once it carries a trailing reason.
  The logical growth is the fixes themselves: `_ThreadState`, `_Override` and `_BoundVerb`
  (B5), `LightApi._lifespan` (B14-004), `_model_class_or_raise` (B4-011), the spelled-out
  `HTTP_METHOD_MIXINS` (B9-002), the typed locals mypy needed where `Any` used to flow.
  Nothing was added that the tracking table does not name.
- **FROZEN classes**: `BaseCache.get/set` and `RedisCache.get/set` keep their behaviour and
  signatures; ruff's autofix changed the spelling of two annotations
  (`Optional[Dict[str, Any]]` -> `dict[str, Any] | None`, strings at runtime under
  `from __future__ import annotations`; `tests/test_public_api.py` still passes), and
  `cache.py` exempts `ARG002` at module level instead of adding comments inside the classes.
- **Per-file ignores** beyond the brief, with the reason in `pyproject.toml`: tests also
  ignore `S105`, `S106`, `S107` (56 literal test passwords) and `E501` (29 long assertions,
  as before); examples also ignore `S101`, `S105`, `SLF001`, `ARG002` and `E501` (smoke
  asserts, demo credentials, `type(self)._model_class` as the docs teach, the documented
  `queryset(self, request)` signature, curl commands). The tests glob is `tests/**/*.py`
  so `tests/integration/` is covered.
- **`filterwarnings = ["error", "ignore::ResourceWarning", ...]`**: every library or
  pytest warning fails the run; `ResourceWarning` keeps Python's default (ignored) because
  the tests build throwaway engines they never `dispose()`, which is test hygiene the brief
  did not ask to change (56 tests would need a teardown).
- **Commit `5e91407`** (B2-001..003) also carries the B9-001 hunk (`if not bases:` instead
  of `if name == "RestEndpoint"`); the tracking table points B9-001 at it.
- **Classes 81 -> 84**: `_ThreadState` (B5-003), `_Override` and `_BoundVerb` (B5-001),
  all private.

### Proposals (not applied: each changes visible behaviour or touches a FROZEN class)

- B1-001: `ConfigurationError` from `from_dict` on an unknown `auth:` value instead of silently no auth.
- B1-008: 422 for a filter value the column type cannot parse instead of passing the string through.
- B1-011: raise from a failed `CREATE TABLE` at `build_app()` instead of a warning plus 500s.
- B6-001: `from_config` builds an `AsyncEngine` when `mode: async` (today `lightapi serve` cannot start an async app).
- B6-002: implement `Cache.vary_on`, which the docs describe and nothing reads, or fix the docs.
- B6-003: `Config.jwt_expiration` is never read; remove in 0.2.0 or make FROZEN `JWTAuthentication` read it.
- B6-004: an `AsyncEngine` without `mode="async"` yields 500s; detect the mode from the engine or refuse at register.
- B6-005: an `async def validate_credentials` on `BasicAuthentication` lets any credentials through; refuse at startup or await it.
- B7-001, B7-002: sync auth backends and `login_validator` run on the event loop; move them to `run_blocking`.
- B7-003: `asyncio.run` on a worker thread while a loop runs (table creation, reflection); refuse and document.
- B11-001, B11-002: CORS `allow_credentials=True` with `*` origins by default; opt-in instead.
- B13-002: filter backends are instantiated per request; once per `Filtering` would share state across threads.
- B15-002: `Authentication.rate_limiter` is stored on the backend and never read; remove in 0.2.0.
