# Refactor log: second OO pass (branch `refactor/oo-second-pass`)

Working notes for the refactor described in the plan of 2026-10-10. One entry per step:
what was done, how it was verified, what comes next. If the work is interrupted, resume
from the last "Next" line.

Base: `origin/test/release-validation` (PR #44) with `origin/refactor/group-loose-symbols`
(PR #45) and `origin/fix/edge-case-500s` (PR #46) merged in. The only merge conflict was the
`lightapi.constants` import line in `lightapi/rest.py`: kept the `ResponseKey` import from
#45 and the `TypeAdapter` import from #46.

## Phase 0: baseline (merged base, commit d24c7f3)

Commands (run from the repo root; `--frozen` keeps `uv.lock` untouched):

```
uv run --frozen --extra dev pytest tests/ -q
uv run --isolated --frozen --python 3.10 --extra dev pytest tests/ -q --cov=lightapi
uv run --frozen --extra dev ruff check lightapi
uv run --frozen --extra dev ruff format --check lightapi
uv run --frozen --extra dev mypy lightapi
uv build && uvx twine check dist/*
```

| Measure | Baseline |
|---|---|
| pytest, Python 3.13 (local `.venv`) | 547 passed, 19 skipped, 1 xfailed, 2 xpassed, 656 warnings |
| pytest, Python 3.10 (`--isolated`) | 547 passed, 19 skipped, 1 xfailed, 2 xpassed, 657 warnings |
| coverage (`--cov=lightapi`, 3.10) | 90% (2136 statements, 213 missed) |
| ruff check / ruff format --check | clean / 35 files formatted |
| mypy lightapi | 0 errors (35 files; `[tool.mypy]` has `ignore_errors` for 18 modules) |
| `uv build` + `twine check` | wheel + sdist built (0.1.27 on this branch; `master` is 0.1.29), both PASSED |
| `lightapi/` size | 35 files, 4647 lines, 69 classes, 2 enums, 72 module-level functions |

The 19 skipped tests are the Postgres/Redis integration tests (`tests/integration/`), which
need `LIGHTAPI_TEST_PG_SYNC`, `LIGHTAPI_TEST_PG_ASYNC` and `LIGHTAPI_REDIS_URL`.

Module-level functions at baseline, by file: `yaml_loader.py` 11, `rest.py` 10,
`schema.py` 7, `lightapi.py` 7, `endpoint_handler.py` 6, `cache.py` 5, `table_mapping.py` 4,
`_login.py` 3, `pagination.py` 3, `session.py` 3, `yaml_names.py` 3, `_dict_config_loader.py`
2, `middleware_runner.py` 2, `repository.py` 2, `fields.py` 1, `filters.py` 1, `server.py` 1,
`yaml_schema.py` 1. Of these, `Field`, `get_sync_session`, `get_async_session`,
`server.main`, `filters._coerce_filter_value` and `cache.invalidate_cache_prefix` are public
or documented and stay.

### HTTP snapshot (Phase 0 step 4)

`examples/18_full_api.py` served by a real uvicorn on 127.0.0.1:18080 (port 8000 was taken
by Docker; the launcher reproduces the example's `__main__` block on another port). 41
requests recorded (status, `content-type`/`allow`/`www-authenticate` headers, raw body with
timestamps and JWTs normalised): `/healthz`, list, create, get, PUT, PATCH, DELETE, 404 (missing
and oversized id), 409 (PUT and PATCH), 422 (missing version, bad version type, empty body,
malformed JSON on POST and PUT), 401 (no token, bad token, bad login), 403, 405 (HEAD on a
collection, PUT on a GET/POST endpoint, POST on a GET-only endpoint, GET on `/auth/login`),
cursor page with a bad cursor, `?page=abc`, filters. Recorded twice: identical. Kept outside
the repo (session scratchpad, `http-before/run.json`) and diffed again in Phase 3.

Differential harness: wheel of this base installed in its own venv, `tools/differential/
record.py` -> 412 steps (`run-base.json`, source fingerprint f11296220501). Phase 3 compares
the final wheel against it with `compare.py`.

## Step 1: characterization tests

`tests/test_second_pass_characterization.py`, 16 tests, all green before any code change:
`WWW-Authenticate: Bearer` on the 401 of JWT and Basic endpoints; a method missing from a
permission dict is public; `/auth/login` GET is 405 with `Allow: POST`; `mode="sync"`
accepted; exact messages for an unknown mode, pagination style and JWT algorithm;
`reflect = "full"` behaves like `True`; malformed JSON on POST and PUT gives the current 422
shapes; an invalid cursor is ignored; HEAD on a detail route is 405 with `Allow`; async PATCH
409 and 422; cached GET and POST still answer when the Redis client raises `ConnectionError`.

## Step 2: leftover dead code

`rest.py` only: dropped the never-read `_meta["reflect"]` key, moved the stdlib and
pydantic imports that lived inside `_is_optional`, `_field_annotations`, `_declared_columns`
and `_parsed_meta` to the module top (no cycle existed), and with them the
`# type: ignore[attr-defined]` on `types.UnionType`. 563 passed, ruff and mypy clean.

## Step 3: enums and the standard library (one commit each)

### 3a. `http.HTTPStatus`

Deleted the `HTTPStatus(int, Enum)` copy in `constants.py`; `rest.py`, `endpoint_handler.py`,
`auth_checker.py` and `_login.py` import the stdlib enum. The raw status integers in
`authentication/basic.py` (401), `core.py` (200, 403), `rate_limiter.py` (429) and
`cache_helper.py` (`== 200`) became members too. `Response.__init__(status_code: int = 200)`
in `core.py` is a public signature and stays. Starlette and h11 take the `IntEnum` as an int,
so the bytes on the wire are the same. 563 passed, ruff and mypy clean.

### 3b. `HttpVerb`

`constants.HttpVerb(str, Enum)` (GET, POST, PUT, PATCH, DELETE, OPTIONS) with `HttpVerb.of()`
for request methods the API never serves (HEAD), and `CRUD_VERBS` replacing
`rest._ALL_METHODS`. Verb dictionaries in `endpoint_handler.py` are keyed by the enum; the
`request.method == "..."` comparisons in `cache_helper.py`, `_login.py`, `core.py` and
`authentication/basic.py` compare against members; `CORSMiddleware` keeps its default list as
a class constant. `RestEndpoint._allowed_methods` stays a set of plain strings (documented
that way) and `HttpMethod.GET._http_method` stays `"GET"` (public marker): the metaclass
validates them through `HttpVerb(...)` and keeps `.value`. Members are never formatted
(`f"{member}"` differs between Python 3.10 and 3.11+). `jwt.py:65` keeps its literal
(FROZEN). Left for Step 8: the name registries in `yaml_names.py` and `_dict_config_loader.py`
that map YAML/dict method names to `HttpMethod` mixins. 563 passed, ruff and mypy clean.

Next: 3c `ExecutionMode`, then `PaginationStyle`, `TableReflection`, `RateLimitWindow`,
`JwtAlgorithm`, `ApiError`.
