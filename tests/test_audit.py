"""Behaviour pinned or changed by the audit (docs/audit.md), one test per tracked ID."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy import select as sa_select
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
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
