"""Behaviour pinned or changed by the audit (docs/audit.md), one test per tracked ID."""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

import pytest
import redis
from sqlalchemy import create_engine
from sqlalchemy import select as sa_select
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import Cache, LightApi, RestEndpoint
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
