"""Behaviour pinned or changed by the audit (docs/audit.md), one test per tracked ID."""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

import pytest
import redis
from sqlalchemy import MetaData, create_engine
from sqlalchemy import select as sa_select
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import Authentication, Cache, JWTAuthentication, LightApi, RestEndpoint
from lightapi.cache import RedisCacheBackend
from lightapi.config import Config
from lightapi.fields import Field as LField

os.environ.setdefault("LIGHTAPI_JWT_SECRET", "audit-secret")


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


class TestB2HidingDefaults:
    def test_endpoint_declared_under_future_annotations_still_maps(self):
        """B2-003: RestEndpoint's own annotations must resolve under get_type_hints,
        or every subclass in a module with `from __future__ import annotations`
        falls back to raw strings and fails with "not in the type map"."""

        class AuditFuture(RestEndpoint):
            title: str = LField(min_length=1)

        client = _client({"/future": AuditFuture})

        assert client.post("/future", json={"title": "ok"}).status_code == 201


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
