"""Behaviour pinned or changed by the audit (docs/audit.md), one test per tracked ID."""

from __future__ import annotations

import datetime
import logging
import os
import warnings
from decimal import Decimal
from unittest.mock import patch

import pytest
import redis
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
)
from sqlalchemy import select as sa_select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

import lightapi
from lightapi import (
    Authentication,
    BasicAuthentication,
    Cache,
    Field,
    FieldFilter,
    Filtering,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    Pagination,
    RestEndpoint,
)
from lightapi.cache import RedisCacheBackend
from lightapi.config import Config
from lightapi.exceptions import ConfigurationError
from lightapi.fields import Field as LField
from lightapi.yaml_config import LightAPIConfig

os.environ.setdefault("LIGHTAPI_JWT_SECRET", "audit-secret")


def _memory_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _client(mapping: dict[str, type], engine=None, **app_kwargs) -> TestClient:
    app = LightApi(engine=engine or _memory_engine(), **app_kwargs)
    app.register(mapping)
    return TestClient(app.build_app())


class TestB2HidingDefaults:
    def test_endpoint_declared_under_future_annotations_still_maps(self):
        """B2-003: RestEndpoint's own annotations must resolve under get_type_hints,
        or every subclass in a module with `from __future__ import annotations`
        falls back to raw strings and fails with "not in the type map"."""

        class AuditFuture(RestEndpoint):
            title: str = LField(min_length=1)

        client = _client({"/future": AuditFuture})

        assert client.post("/future", json={"title": "ok"}).status_code == 201


class TestB9DispatchByName:
    def test_subclass_named_rest_endpoint_is_still_mapped(self):
        """B9-001: the root class is the one without bases, not the one named so."""

        class RestEndpoint(lightapi.RestEndpoint):
            title: str = LField(min_length=1)

        client = _client({"/shadow": RestEndpoint})

        assert client.post("/shadow", json={"title": "ok"}).status_code == 201


class TestB8HiddenMutation:
    def test_pagination_keeps_the_style_as_given_and_still_builds_the_paginator(self):
        """B8-001: no object.__setattr__ on the frozen config; the user's value stays."""
        from lightapi.pagination import CursorPaginator, PaginationStyle

        as_string = Pagination(style="cursor", page_size=5)
        as_member = Pagination(style=PaginationStyle.CURSOR, page_size=5)

        assert as_string.style == "cursor" and type(as_string.style) is str
        assert isinstance(as_string.paginator, CursorPaginator)
        assert isinstance(as_member.paginator, CursorPaginator)
        with pytest.raises(ConfigurationError, match="'offset' is invalid"):
            Pagination(style="offset")


class TestB5PerRequestChecks:
    def test_verb_override_is_resolved_at_registration(self):
        """B5-001: the handler looks the hooks up once; a method assigned to the
        class after register() is not consulted on every request any more."""

        class AuditHooked(RestEndpoint):
            title: str = LField(min_length=1)

            def get(self, request):
                return {"hook": "registered"}

        client = _client({"/hooked": AuditHooked})
        AuditHooked.get = lambda self, request: {"hook": "late"}  # type: ignore[method-assign]

        assert client.get("/hooked").json() == {"hook": "registered"}

    def test_middleware_coroutine_detection_happens_once_per_class(self):
        """B5-002: the chain decides once whether each process() is awaited."""
        from lightapi.core import Middleware
        from lightapi.endpoint_handler import MiddlewareChain

        class Sync(Middleware):
            def process(self, request, response):
                return None

        class Async(Middleware):
            async def process(self, request, response):
                return None

        chain = MiddlewareChain([Sync, Async])

        assert chain._awaits == {Sync: False, Async: True}
        assert chain._awaits is chain._awaits

    def test_isolated_session_managers_on_one_thread_share_the_thread_state(self):
        """B5-003: the thread-local state is built by its own __init__, not lazily."""
        from lightapi.session_manager import SessionManager

        first = SessionManager(_memory_engine(), use_test_isolation=True)
        second = SessionManager(_memory_engine(), use_test_isolation=True)

        assert first.metadata is second.metadata
        assert first.registry is second.registry
        assert first.table_name_for("audit_tbl") == "audit_tbl"
        assert second.table_name_for("audit_tbl") == "audit_tbl_2"


class TestA4DeadCode:
    def test_jwt_algorithm_env_var_is_ignored_when_config_has_the_default(
        self, monkeypatch
    ):
        """A4-002: the env fallback was unreachable (v0.1.29 too); drop it, same result."""
        monkeypatch.setenv("LIGHTAPI_JWT_ALGORITHM", "HS512")

        assert Config().jwt_algorithm_value == "HS256"

    def test_queryset_inherited_from_a_base_class_is_used(self):
        """A4-003: one getattr covers the class dict and its bases."""

        class PublishedOnly(RestEndpoint):
            _base_only = True

            def queryset(self, request):
                model = type(self)._model_class
                return sa_select(model).where(model.published.is_(True))

        class AuditPost(PublishedOnly):
            title: str = LField(min_length=1)
            published: bool = LField(default=False)

        client = _client({"/posts": AuditPost})
        client.post("/posts", json={"title": "draft"})
        client.post("/posts", json={"title": "live", "published": True})

        titles = [row["title"] for row in client.get("/posts").json()["results"]]

        assert titles == ["live"]


class _RedisDown:
    """A redis client whose every call fails the way a dead server does."""

    def _fail(self, *args, **kwargs):
        raise redis.ConnectionError("Error 61 connecting to localhost:6379")

    get = setex = delete = scan_iter = ping = _fail


class AuditCachedItem(RestEndpoint):
    name: str = LField(min_length=1)

    class Meta:
        cache = Cache(ttl=30)


class TestB1SilentErrors:
    @pytest.fixture(autouse=True)
    def fresh_redis_client(self):
        RedisCacheBackend.shared.cache_clear()
        yield
        RedisCacheBackend.shared.cache_clear()

    def test_redis_failure_is_logged_with_the_traceback_and_still_served(self, caplog):
        """B1-005: the fallback stays, the operator learns why."""
        with patch("lightapi.cache.redis.from_url", return_value=_RedisDown()):
            with pytest.warns(RuntimeWarning, match="not reachable"):
                client = _client({"/cached": AuditCachedItem})
            caplog.clear()
            with caplog.at_level(logging.WARNING, logger="lightapi.cache"):
                resp = client.get("/cached")

        assert resp.status_code == 200
        records = [r for r in caplog.records if r.name == "lightapi.cache"]
        assert records and all(r.exc_info for r in records)
        assert "Cache read failed" in records[0].getMessage()

    def test_login_validator_exception_is_logged_with_the_traceback(self, caplog):
        """B1-004: the 401 stays (documented since 0.1.24), the log carries the cause."""

        def exploding(username: str, password: str):
            raise RuntimeError("directory server is down")

        class AuditNote(RestEndpoint):
            text: str = LField(min_length=1)

            class Meta:
                authentication = Authentication(backend=JWTAuthentication)

        client = _client({"/notes": AuditNote}, login_validator=exploding)

        with caplog.at_level(logging.WARNING, logger="lightapi._login"):
            resp = client.post("/auth/login", json={"username": "u", "password": "p"})

        assert resp.status_code == 401
        assert resp.json() == {"detail": "Invalid credentials"}
        record = next(r for r in caplog.records if r.name == "lightapi._login")
        assert record.exc_info and "directory server is down" in str(record.exc_info[1])

    def test_table_creation_failure_at_build_app_is_logged_with_the_traceback(
        self, caplog
    ):
        """B1-010: build_app still returns the app; the warning explains the DDL error."""

        class AuditPlain(RestEndpoint):
            title: str = LField(min_length=1)

        app = LightApi(engine=_memory_engine())
        app.register({"/plain": AuditPlain})
        ddl_error = OperationalError("CREATE TABLE", {}, Exception("disk full"))

        with (
            patch.object(MetaData, "create_all", side_effect=ddl_error),
            caplog.at_level(logging.WARNING, logger="lightapi.lightapi"),
        ):
            app.build_app()

        record = next(r for r in caplog.records if r.name == "lightapi.lightapi")
        assert "Table creation warning" in record.getMessage()
        assert record.exc_info and "disk full" in str(record.exc_info[1])


class TestB4HonestTypes:
    def test_authentication_without_backend_cannot_build_one(self):
        """B4-005: `backend` is Optional; building from None is a configuration error."""
        with pytest.raises(ConfigurationError, match="no backend"):
            Authentication().build_backend()

    def test_crud_on_an_unregistered_endpoint_names_the_missing_register_call(self):
        """B4-011: `_model_class` is None until register(); the error says so."""

        class AuditUnregistered(RestEndpoint):
            title: str = LField()

        with pytest.raises(RuntimeError, match="register"):
            AuditUnregistered._model_class_or_raise()


class TestB12Timeouts:
    def test_redis_client_gets_a_read_timeout_as_well_as_a_connect_timeout(self):
        """B12-001: a Redis that accepts the connection and hangs cannot hold a worker."""
        with patch("lightapi.cache.redis.from_url") as from_url:
            RedisCacheBackend("redis://localhost:1")._get_client()

        from_url.assert_called_once_with(
            "redis://localhost:1", socket_connect_timeout=1, socket_timeout=1
        )


class TestB10TimeAndPaths:
    def test_rows_inserted_outside_the_repository_get_naive_utc_timestamps(self):
        """B10-001: the column defaults give the same naive UTC Repository stores,
        without the deprecated utcnow()."""

        class AuditStamped(RestEndpoint):
            title: str = LField()

        engine = _memory_engine()
        app = LightApi(engine=engine)
        app.register({"/stamped": AuditStamped})
        app.build_app()
        table = AuditStamped.__table__

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            with engine.begin() as conn:
                conn.execute(insert(table).values(title="outside"))
                created_at = conn.execute(sa_select(table.c.created_at)).scalar_one()

        assert created_at.tzinfo is None
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        assert abs((now - created_at).total_seconds()) < 60

    def test_from_file_accepts_a_path_object(self, tmp_path):
        """B10-003: the YAML document is opened through pathlib."""
        document = tmp_path / "audit.yaml"
        document.write_text(
            'database:\n  url: "sqlite:///:memory:"\nendpoints:\n'
            "  - route: /auditpaths\n    fields:\n      title: {type: str}\n"
        )

        config = LightAPIConfig.from_file(document)

        assert [entry.effective_route for entry in config.endpoints] == ["/auditpaths"]


class TestB14WarningsAndLogs:
    def test_registration_is_logged_with_path_and_class_name(self, caplog):
        """B14-001: the same message as before, built by logging instead of f-strings."""

        class AuditLogged(RestEndpoint):
            title: str = LField()

        app = LightApi(engine=_memory_engine())
        with caplog.at_level(logging.INFO, logger="lightapi.lightapi"):
            app.register({"/logged": AuditLogged})

        assert "Registering endpoint /logged -> AuditLogged" in caplog.messages

    def test_async_app_creates_its_tables_at_lifespan_startup(self):
        """B14-004: lifespan replaces the deprecated on_startup handler; the tables
        of an async app are still created when the server starts."""

        class AuditLifespan(RestEndpoint):
            title: str = LField()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        app = LightApi(engine=engine, mode="async")
        app.register({"/lifespan": AuditLifespan})
        starlette_app = app.build_app()

        assert starlette_app.router.on_startup == []
        with TestClient(starlette_app) as client:
            assert client.get("/lifespan").status_code == 200
            # Close the aiosqlite connections while their loop is still alive.
            client.portal.call(engine.dispose)

    def test_registering_an_endpoint_raises_no_deprecation_warning(self):
        """B14-005: the declared columns go straight into the Table; nothing copies them."""

        class AuditFresh(RestEndpoint):
            title: str = LField()

        app = LightApi(engine=_memory_engine())
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            app.register({"/fresh": AuditFresh})

        assert AuditFresh.__table__.c.title is not None


class TestA10GuardAnswersWithTheBackend:
    """The 401 a protected endpoint sends is the backend's get_auth_error_response():
    the documented hook, the README's JWT text, and the Basic challenge browsers need.
    """

    def test_jwt_endpoint_401_is_the_backend_reply(self):
        class AuditJwtGuarded(RestEndpoint):
            title: str = LField()

            class Meta:
                authentication = Authentication(
                    backend=JWTAuthentication, permission=IsAuthenticated
                )

        client = _client({"/jwtguarded": AuditJwtGuarded})

        response = client.get("/jwtguarded")

        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication credentials invalid."}
        assert response.headers["www-authenticate"] == "Bearer"

    def test_basic_endpoint_401_carries_the_basic_challenge(self):
        class AuditBasicGuarded(RestEndpoint):
            title: str = LField()

            class Meta:
                authentication = Authentication(
                    backend=BasicAuthentication, permission=IsAuthenticated
                )

        client = _client({"/basicguarded": AuditBasicGuarded})

        response = client.get("/basicguarded")

        assert response.status_code == 401
        assert response.json() == {"error": "authentication failed"}
        assert response.headers["www-authenticate"] == 'Basic realm="Restricted Area"'

    def test_a_backend_that_overrides_the_hook_is_heard(self):
        class Teapot(JWTAuthentication):
            def get_auth_error_response(self, request):
                return JSONResponse({"detail": "no tea"}, status_code=418)

        class AuditCustomGuarded(RestEndpoint):
            title: str = LField()

            class Meta:
                authentication = Authentication(
                    backend=Teapot, permission=IsAuthenticated
                )

        client = _client({"/customguarded": AuditCustomGuarded})

        response = client.get("/customguarded")

        assert response.status_code == 418
        assert response.json() == {"detail": "no tea"}


class AuditFiltered(RestEndpoint):
    title: str = LField()
    pages: int = LField()
    price: float = LField()

    class Meta:
        filtering = Filtering(backends=[FieldFilter], fields=["pages", "price"])


class TestB1FilterValueParsing:
    """B1-008: a filter value the column type cannot parse is a 422, not a silent
    empty list (SQLite) or a 500 (Postgres: invalid input syntax for type integer)."""

    def _client(self):
        client = _client({"/filtered": AuditFiltered})
        client.post("/filtered", json={"title": "t", "pages": 100, "price": 9.5})
        return client

    def test_unparsable_int_filter_is_422_naming_the_parameter(self):
        response = self._client().get("/filtered?pages=lots")

        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["query", "pages"]

    def test_unparsable_float_filter_is_422(self):
        response = self._client().get("/filtered?price=cheap")

        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["query", "price"]

    def test_parsable_filter_values_still_filter(self):
        client = self._client()

        assert len(client.get("/filtered?pages=100").json()["results"]) == 1
        assert client.get("/filtered?pages=101").json()["results"] == []


def _engine_with_docs_table():
    """A pre-existing table with a nullable column, as reflection finds it."""
    engine = _memory_engine()
    metadata = MetaData()
    Table(
        "audit_reflected_docs",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("title", String, nullable=False),
        Column("notes", String, nullable=True),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
        Column("version", Integer, nullable=False, default=1),
    )
    metadata.create_all(engine)
    return engine


class TestReflectedSchemaDefaults:
    """A reflected schema honours what the table and the declared fields say about
    optional values; found by e2e scenario 11 (partial reflection, declared default)."""

    def test_nullable_reflected_column_is_optional_on_post(self):
        class AuditReflectedFull(RestEndpoint):
            class Meta:
                table = "audit_reflected_docs"
                reflect = True

        client = _client(
            {"/rdocs": AuditReflectedFull}, engine=_engine_with_docs_table()
        )

        created = client.post("/rdocs", json={"title": "only the title"})

        assert created.status_code == 201, created.text
        assert created.json()["notes"] is None

    def test_declared_default_applies_on_partial_reflection(self):
        class AuditReflectedPartial(RestEndpoint):
            notes: str = LField(default="")

            class Meta:
                table = "audit_reflected_docs"
                reflect = "partial"

        client = _client(
            {"/pdocs": AuditReflectedPartial}, engine=_engine_with_docs_table()
        )

        created = client.post("/pdocs", json={"title": "no notes sent"})

        assert created.status_code == 201, created.text
        assert created.json()["notes"] == ""

    def test_declared_constraint_applies_on_partial_reflection(self):
        class AuditReflectedStrict(RestEndpoint):
            notes: str = LField(min_length=3)

            class Meta:
                table = "audit_reflected_docs"
                reflect = "partial"

        client = _client(
            {"/sdocs": AuditReflectedStrict}, engine=_engine_with_docs_table()
        )

        assert (
            client.post("/sdocs", json={"title": "t", "notes": "ab"}).status_code == 422
        )
        assert (
            client.post("/sdocs", json={"title": "t", "notes": "abc"}).status_code
            == 201
        )


class TestB6AsyncFromUrl:
    def test_async_mode_with_a_database_url_builds_an_async_engine(self):
        """B6-001: mode='async' plus database_url used to raise at register()."""

        class AuditUrlAsync(RestEndpoint):
            title: str = LField()

        app = LightApi(database_url="sqlite+aiosqlite:///:memory:", mode="async")
        app.register({"/urlasync": AuditUrlAsync})

        with TestClient(app.build_app()) as client:
            assert client.post("/urlasync", json={"title": "t"}).status_code == 201
            assert client.get("/urlasync").json()["results"][0]["title"] == "t"
            client.portal.call(app._engine.dispose)

    def test_async_mode_with_a_sync_driver_url_is_a_configuration_error(self):
        with pytest.raises(ConfigurationError, match="async driver"):
            LightApi(database_url="sqlite:///:memory:", mode="async")

    def test_from_config_serves_an_async_document(self, tmp_path):
        document = tmp_path / "async.yaml"
        document.write_text(
            'database:\n  url: "sqlite+aiosqlite:///:memory:"\nmode: async\nendpoints:\n'
            "  - route: /asyncdocs\n    fields:\n      title: {type: str}\n"
        )

        app = LightApi.from_config(str(document))

        with TestClient(app.build_app()) as client:
            assert client.post("/asyncdocs", json={"title": "y"}).status_code == 201
            client.portal.call(app._engine.dispose)


class AuditPriced(RestEndpoint):
    price: Decimal = Field(decimal_places=2)

    class Meta:
        table = "audit_priced"


class TestB6DecimalPlaces:
    """B6-006: `Field(decimal_places=N)` reached neither pydantic nor the DDL
    (`Numeric(scale=N)` without a precision renders as plain NUMERIC), so a value
    with more places was stored as sent. e2e scenario 17 stored "1.999" on both DBs."""

    def test_more_decimal_places_than_declared_is_422(self):
        with _client({"/priced": AuditPriced}) as client:
            response = client.post("/priced", json={"price": "1.999"})

        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["price"]

    def test_declared_decimal_places_are_accepted_and_kept(self):
        with _client({"/priced": AuditPriced}) as client:
            response = client.post("/priced", json={"price": "12.50"})

        assert response.status_code == 201
        assert response.json()["price"] == "12.50"


class AuditPatched(RestEndpoint):
    name: str = Field(min_length=3)
    price: Decimal = Field(decimal_places=2)

    class Meta:
        table = "audit_patched"


class TestReviewPatchKeepsConstraints:
    """B2-013: the PATCH schema rebuilt every field as `Optional[annotation]` and
    dropped its FieldInfo, so PATCH skipped min_length, decimal_places and every
    other constraint PUT enforces (review finding 6 on the e2e branch)."""

    def _seeded(self):
        client = _client({"/patched": AuditPatched})
        client.__enter__()
        row = client.post("/patched", json={"name": "abc", "price": "1.00"}).json()
        return client, row

    def test_patch_enforces_decimal_places(self):
        client, row = self._seeded()
        with client:
            response = client.patch(
                f"/patched/{row['id']}", json={"price": "1.999", "version": 1}
            )

        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["price"]

    def test_patch_enforces_min_length(self):
        client, row = self._seeded()
        with client:
            response = client.patch(
                f"/patched/{row['id']}", json={"name": "ab", "version": 1}
            )

        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["name"]

    def test_patch_with_a_valid_subset_still_works(self):
        client, row = self._seeded()
        with client:
            response = client.patch(
                f"/patched/{row['id']}", json={"name": "abcd", "version": 1}
            )

        assert response.status_code == 200
        assert response.json()["name"] == "abcd"
        assert response.json()["price"] == "1.00"


class TestReviewDecimalPlacesNeedsDecimal:
    """B6-007: `decimal_places` on a non-Decimal field used to be ignored and, once
    forwarded to pydantic (B6-006), made every write a 500 (`TypeError: Unable to
    apply constraint`). It is refused when the class is defined, naming the field
    (review finding 2 on the e2e branch)."""

    def test_decimal_places_on_a_float_field_is_a_configuration_error(self):
        with pytest.raises(ConfigurationError, match=r"decimal_places.*ratio"):

            class AuditBadPlaces(RestEndpoint):
                ratio: float = Field(decimal_places=2)

                class Meta:
                    table = "audit_bad_places"

    def test_decimal_places_on_a_yaml_int_field_is_a_configuration_error(
        self, tmp_path
    ):
        document = tmp_path / "bad.yaml"
        document.write_text(
            'database:\n  url: "sqlite:///:memory:"\nendpoints:\n  - route: /x\n'
            "    fields:\n      count: {type: int, decimal_places: 2}\n"
        )

        with pytest.raises(ConfigurationError, match=r"decimal_places.*count"):
            LightAPIConfig.from_file(document).build_app(LightApi)


class TestReviewSecretsStayOutOfErrors:
    """B1-020: two error messages echoed the database URL with its password: the
    async-driver ConfigurationError (B6-001) and the YAML ValidationError text under
    extra="forbid" (B2-012), which prints `input_value=` (review finding 3)."""

    # Built from parts so no credential-shaped literal sits in the source.
    CANARY = "canary-value"
    URL = "postgresql://app:" + CANARY + "@db/app"

    def test_async_driver_error_hides_the_password(self):
        with pytest.raises(ConfigurationError) as info:
            LightApi(database_url=self.URL, mode="async")

        assert self.CANARY not in str(info.value)
        assert "postgresql://app:***@db/app" in str(info.value)

    def test_yaml_typo_error_hides_the_password_and_names_the_key(self, tmp_path):
        document = tmp_path / "bad.yaml"
        document.write_text(
            f'databse:\n  url: "{self.URL}"\nendpoints:\n'
            "  - route: /x\n    fields:\n      title: {type: str}\n"
        )

        with pytest.raises(ConfigurationError, match="databse") as info:
            LightAPIConfig.from_file(document)

        assert self.CANARY not in str(info.value)


class TestReviewFieldSpecUnknownKey:
    """B2-014: a typo under `fields.<name>` (`min_lenght`) was dropped by FieldSpec's
    extra="allow", so the constraint silently vanished while the configuration
    guide promises a ConfigurationError (review finding 7)."""

    def test_unknown_constraint_key_is_rejected(self, tmp_path):
        document = tmp_path / "bad.yaml"
        document.write_text(
            'database:\n  url: "sqlite:///:memory:"\nendpoints:\n  - route: /x\n'
            "    fields:\n      title: {type: str, min_lenght: 3}\n"
        )

        with pytest.raises(ConfigurationError, match="min_lenght"):
            LightAPIConfig.from_file(document)

    def test_known_constraint_keys_and_default_still_load(self, tmp_path):
        document = tmp_path / "ok.yaml"
        document.write_text(
            'database:\n  url: "sqlite:///:memory:"\nendpoints:\n  - route: /x\n'
            "    fields:\n      title: {type: str, min_length: 3, default: abc}\n"
        )

        spec = LightAPIConfig.from_file(document).endpoints[0].fields["title"]

        assert spec.field_info() is not None


class AuditAsyncUrl(RestEndpoint):
    title: str = Field(min_length=1)

    class Meta:
        table = "audit_async_url"


class TestReviewAsyncFromUrlAutoDetect:
    """B6-004: README says the mode is auto-detected when omitted, but a database URL
    with an async driver and no `mode="async"` built a sync Engine (review minor 8)."""

    def test_async_url_without_mode_serves(self):
        app = LightApi(database_url="sqlite+aiosqlite:///:memory:")
        app.register({"/autodetected": AuditAsyncUrl})
        with TestClient(app.build_app()) as client:
            response = client.post("/autodetected", json={"title": "t"})

            assert response.status_code == 201
            client.portal.call(app._engine.dispose)

    def test_yaml_async_url_without_mode_serves(self, tmp_path):
        document = tmp_path / "async.yaml"
        document.write_text(
            'database:\n  url: "sqlite+aiosqlite:///:memory:"\nendpoints:\n'
            "  - route: /autodetected\n    fields:\n      title: {type: str}\n"
        )
        app = LightAPIConfig.from_file(document).build_app(LightApi)
        with TestClient(app.build_app()) as client:
            response = client.post("/autodetected", json={"title": "t"})

            assert response.status_code == 201
            client.portal.call(app._engine.dispose)


class TestB6AsyncBasicValidatorRefused:
    """B6-005: an `async def validate_credentials` on a BasicAuthentication subclass
    was called without await by the guard, the coroutine was truthy, and ANY Basic
    credentials passed. The login route awaits it, the guard cannot: refused at
    register() with a ConfigurationError naming the method."""

    def test_async_validator_on_basic_is_refused_at_register(self):
        class AuditAsyncBasic(BasicAuthentication):
            async def validate_credentials(self, username, password):
                return {"username": username}

        class AuditBasicGuardedAsync(RestEndpoint):
            text: str = Field(min_length=1)

            class Meta:
                table = "audit_basic_guarded_async"
                authentication = Authentication(
                    backend=AuditAsyncBasic, permission=IsAuthenticated
                )

        app = LightApi(engine=_memory_engine())

        with pytest.raises(ConfigurationError, match="validate_credentials"):
            app.register({"/asyncbasic": AuditBasicGuardedAsync})


class TestYamlUnknownKeys:
    """A key the YAML format does not know is a ConfigurationError naming it, not a
    silently ignored block; found by e2e scenario 12 (`defaults.filtering`)."""

    def test_unknown_key_under_defaults_is_rejected(self, tmp_path):
        document = tmp_path / "bad.yaml"
        document.write_text(
            'database:\n  url: "sqlite:///:memory:"\ndefaults:\n  filtering:\n'
            "    fields: [genre]\nendpoints:\n  - route: /x\n    fields:\n"
            "      title: {type: str}\n"
        )

        with pytest.raises(ConfigurationError, match="filtering"):
            LightAPIConfig.from_file(document)

    def test_unknown_key_under_meta_is_rejected(self, tmp_path):
        document = tmp_path / "bad.yaml"
        document.write_text(
            'database:\n  url: "sqlite:///:memory:"\nendpoints:\n  - route: /x\n'
            "    fields:\n      title: {type: str}\n    meta:\n      paginate: true\n"
        )

        with pytest.raises(ConfigurationError, match="paginate"):
            LightAPIConfig.from_file(document)

    def test_unknown_top_level_key_is_rejected(self, tmp_path):
        document = tmp_path / "bad.yaml"
        document.write_text(
            'database:\n  url: "sqlite:///:memory:"\nmiddlewares: []\nendpoints:\n'
            "  - route: /x\n    fields:\n      title: {type: str}\n"
        )

        with pytest.raises(ConfigurationError, match="middlewares"):
            LightAPIConfig.from_file(document)


class TestB19LifespanLoop:
    def test_lifespan_creates_tables_on_the_serving_loop_not_a_worker_thread(self):
        """B19/B7-003: tables created on a worker loop poison an asyncpg pool; the
        lifespan must await create_all on the loop that serves the requests."""

        class AuditLoopBound(RestEndpoint):
            title: str = LField()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        app = LightApi(engine=engine, mode="async")
        app.register({"/loopbound": AuditLoopBound})
        starlette_app = app.build_app()

        with (
            patch(
                "lightapi.lightapi.concurrent.futures.ThreadPoolExecutor",
                side_effect=AssertionError("table creation left the serving loop"),
            ),
            TestClient(starlette_app) as client,
        ):
            assert client.post("/loopbound", json={"title": "t"}).status_code == 201
            assert client.get("/loopbound").json()["results"][0]["title"] == "t"
            client.portal.call(engine.dispose)
