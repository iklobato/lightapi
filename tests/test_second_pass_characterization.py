"""Pins behaviour the second OO refactor pass touches and no other test covered.

Each test fixes what the code does today, so the refactor can only change the
code's shape, not its answers.
"""

from __future__ import annotations

import datetime
import os
from unittest.mock import patch

import pytest
import pytest_asyncio
import redis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import (
    Authentication,
    BasicAuthentication,
    Cache,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    Pagination,
    RestEndpoint,
)
from lightapi import cache as cache_module
from lightapi.auth import AllowAny
from lightapi.config import Config
from lightapi.exceptions import ConfigurationError
from lightapi.fields import Field as LField

os.environ.setdefault("LIGHTAPI_JWT_SECRET", "second-pass-secret")


def _memory_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _client(mapping: dict[str, type], **app_kwargs) -> TestClient:
    app = LightApi(engine=_memory_engine(), **app_kwargs)
    app.register(mapping)
    return TestClient(app.build_app())


class JwtNote(RestEndpoint):
    text: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(backend=JWTAuthentication)


class BasicNote(RestEndpoint):
    text: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(backend=BasicAuthentication)


class PostOnlyLogin(RestEndpoint):
    """GET is public because the permission dict has no entry for it."""

    text: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication, permission={"POST": IsAuthenticated}
        )


class CursorItem(RestEndpoint):
    label: str = LField(min_length=1)

    class Meta:
        pagination = Pagination(style="cursor", page_size=2)


class PlainItem(RestEndpoint):
    title: str = LField(min_length=1)


class CachedItem(RestEndpoint):
    name: str = LField(min_length=1)

    class Meta:
        cache = Cache(ttl=30)


class TestAuthenticationResponses:
    def test_jwt_endpoint_without_token_returns_401_with_bearer_challenge(self):
        client = _client({"/notes": JwtNote})

        resp = client.get("/notes")

        assert resp.status_code == 401
        assert resp.headers["WWW-Authenticate"] == "Bearer"
        assert resp.json() == {"detail": "Authentication required"}

    def test_basic_endpoint_without_credentials_returns_401_with_bearer_challenge(
        self,
    ):
        client = _client({"/notes": BasicNote})

        resp = client.get("/notes")

        assert resp.status_code == 401
        assert resp.headers["WWW-Authenticate"] == "Bearer"
        assert resp.json() == {"detail": "Authentication required"}

    def test_method_missing_from_permission_dict_is_public(self):
        client = _client({"/notes": PostOnlyLogin})

        public = client.get("/notes")
        protected = client.post("/notes", json={"text": "x"})

        assert public.status_code == 200
        assert protected.status_code == 401

    def test_login_route_rejects_get_with_allow_post(self):
        client = _client({"/notes": JwtNote})

        resp = client.get("/auth/login")

        assert resp.status_code == 405
        assert resp.headers["Allow"] == "POST"

    def test_login_with_invalid_utf8_body_returns_422(self):
        """Decided in the second pass: this used to be a 500."""
        client = _client({"/notes": JwtNote})

        resp = client.post(
            "/auth/login",
            content=b"\xff\xfe",
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == 422
        assert resp.json()["detail"][0]["loc"] == ["username"]

    def test_backend_is_built_once_per_route_not_per_request(self):
        """Decided in the second pass: before, every request built a new backend."""
        built = []

        class CountingBackend(JWTAuthentication):
            @classmethod
            def from_config(cls, authentication, login_validator=None):
                built.append(cls)
                return cls()

        class Counted(RestEndpoint):
            text: str = LField(min_length=1)

            class Meta:
                authentication = Authentication(backend=CountingBackend)

        client = _client({"/counted": Counted})
        built.clear()

        client.get("/counted")
        client.get("/counted")

        assert len(built) == 1

    def test_permission_subclassing_allowany_does_not_require_login(self):
        """Decided in the second pass: the permission says whether login is needed.

        Before, only AllowAny itself (by identity) made a method public."""

        class Open(AllowAny):
            pass

        class OpenNote(RestEndpoint):
            text: str = LField(min_length=1)

            class Meta:
                authentication = Authentication(
                    backend=JWTAuthentication, permission=Open
                )

        client = _client({"/open": OpenNote})

        assert client.get("/open").status_code == 200


class TestClosedSetsAcceptedAsStrings:
    def test_mode_sync_string_is_accepted(self):
        app = LightApi(engine=_memory_engine(), mode="sync")
        app.register({"/items": PlainItem})

        resp = TestClient(app.build_app()).get("/items")

        assert resp.status_code == 200

    def test_unknown_mode_raises_configuration_error_with_exact_message(self):
        with pytest.raises(ConfigurationError) as exc_info:
            LightApi(engine=_memory_engine(), mode="threaded")

        assert str(exc_info.value) == "mode must be 'sync' or 'async', got 'threaded'"

    def test_unknown_pagination_style_raises_with_exact_message(self):
        with pytest.raises(ConfigurationError) as exc_info:
            Pagination(style="offset")

        assert str(exc_info.value) == (
            "Pagination style 'offset' is invalid. "
            "Choose from: ('page_number', 'cursor')"
        )

    def test_unknown_jwt_algorithm_raises_with_exact_message(self):
        config = Config(jwt_algorithm="none")

        with pytest.raises(ConfigurationError) as exc_info:
            config.jwt_algorithm_value

        assert str(exc_info.value) == (
            "Invalid JWT algorithm 'none'. Valid algorithms are: "
            "['ES256', 'ES384', 'ES512', 'HS256', 'HS384', 'HS512', "
            "'RS256', 'RS384', 'RS512']"
        )

    def test_reflect_full_string_reflects_the_table_like_true(self):
        engine = _memory_engine()
        meta = MetaData()
        Table(
            "legacy_full",
            meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("name", String, nullable=False),
            Column("created_at", DateTime, default=datetime.datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.datetime.utcnow),
            Column("version", Integer, default=1, nullable=False),
        )
        meta.create_all(engine)

        class LegacyFull(RestEndpoint):
            class Meta:
                reflect = "full"
                table = "legacy_full"

        app = LightApi(engine=engine)
        app.register({"/legacy": LegacyFull})
        client = TestClient(app.build_app())

        created = client.post("/legacy", json={"name": "old row"})

        assert created.status_code == 201
        assert created.json()["name"] == "old row"
        assert client.get("/legacy").json()["results"][0]["id"] == created.json()["id"]

    def test_unknown_reflect_value_raises_configuration_error(self):
        """Decided in the second pass: before, `reflect = "yes"` silently built a
        table with only the automatic columns."""
        with pytest.raises(ConfigurationError) as exc_info:

            class Broken(RestEndpoint):
                name: str = LField(min_length=1)

                class Meta:
                    reflect = "yes"

        assert str(exc_info.value) == (
            "Meta.reflect must be True, False, 'full' or 'partial', got 'yes'."
        )


class TestRequestBodyAndPagination:
    def test_post_with_malformed_json_body_returns_422_field_required(self):
        client = _client({"/items": PlainItem})

        resp = client.post(
            "/items", content=b"{not json", headers={"Content-Type": "application/json"}
        )

        assert resp.status_code == 422
        assert resp.json()["detail"][0]["loc"] == ["title"]
        assert resp.json()["detail"][0]["type"] == "missing"

    def test_put_with_malformed_json_body_returns_422_missing_version(self):
        client = _client({"/items": PlainItem})
        pk = client.post("/items", json={"title": "a"}).json()["id"]

        resp = client.put(
            f"/items/{pk}",
            content=b"{not json",
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == 422
        assert resp.json() == {
            "detail": [{"loc": ["version"], "msg": "Field required", "type": "missing"}]
        }

    def test_invalid_cursor_is_ignored_and_first_page_is_returned(self):
        client = _client({"/items": CursorItem})
        for label in ("a", "b", "c"):
            client.post("/items", json={"label": label})

        resp = client.get("/items?cursor=%25%25not-a-cursor")

        assert resp.status_code == 200
        assert [row["label"] for row in resp.json()["results"]] == ["a", "b"]
        assert resp.json()["next"] is not None

    def test_head_on_detail_route_returns_405_with_allow_header(self):
        client = _client({"/items": PlainItem})

        resp = client.head("/items/1")

        assert resp.status_code == 405
        assert resp.headers["Allow"] == "DELETE, GET, PATCH, PUT"


class TestAsyncVersioning:
    @pytest_asyncio.fixture
    async def async_client(self):
        class Widget(RestEndpoint):
            name: str = LField(min_length=1)

            class Meta:
                authentication = Authentication(permission=AllowAny)

        app = LightApi(
            engine=create_async_engine("sqlite+aiosqlite:///:memory:"), mode="async"
        )
        app.register({"/widgets": Widget})
        async with AsyncClient(
            transport=ASGITransport(app=app.build_app()), base_url="http://test"
        ) as client:
            yield client

    async def test_async_patch_with_stale_version_returns_409(self, async_client):
        pk = (await async_client.post("/widgets", json={"name": "w"})).json()["id"]

        resp = await async_client.patch(
            f"/widgets/{pk}", json={"name": "w2", "version": 999}
        )

        assert resp.status_code == 409
        assert resp.json() == {"detail": "version conflict"}

    async def test_async_patch_without_version_returns_422(self, async_client):
        pk = (await async_client.post("/widgets", json={"name": "w"})).json()["id"]

        resp = await async_client.patch(f"/widgets/{pk}", json={"name": "w2"})

        assert resp.status_code == 422
        assert resp.json() == {
            "detail": [{"loc": ["version"], "msg": "Field required", "type": "missing"}]
        }


class _RedisDown:
    """A redis client whose every call fails the way a dead server does."""

    def _fail(self, *args, **kwargs):
        raise redis.ConnectionError("Error 61 connecting to localhost:6379")

    get = setex = delete = scan_iter = ping = _fail


class TestCacheWithRedisDown:
    @pytest.fixture(autouse=True)
    def fresh_redis_client(self):
        cache_module._default_backend.cache_clear()
        yield
        cache_module._default_backend.cache_clear()

    def test_cached_get_and_write_succeed_when_redis_connection_fails(self):
        with patch("lightapi.cache.redis.from_url", return_value=_RedisDown()):
            with pytest.warns(RuntimeWarning, match="not reachable"):
                client = _client({"/cached": CachedItem})

            created = client.post("/cached", json={"name": "n"})
            listed = client.get("/cached")
            listed_again = client.get("/cached")

        assert created.status_code == 201
        assert listed.status_code == 200
        assert listed_again.json()["results"][0]["name"] == "n"
