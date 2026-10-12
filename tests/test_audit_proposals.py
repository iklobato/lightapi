"""The ten `proposta` rows of docs/audit.md, applied on 2026-10-12 at Henry's request.

One class per row. Each test names the behaviour a reasonable user of the
documented feature gets after the fix, and failed before it.
"""

from __future__ import annotations

import asyncio
import base64
import datetime
from unittest.mock import patch

import jwt
import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import (
    AllowAny,
    Authentication,
    BasicAuthentication,
    Cache,
    Field,
    Filtering,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    RateLimiter,
    RestEndpoint,
)
from lightapi.config import config
from lightapi.core import CORSMiddleware
from lightapi.exceptions import ConfigurationError
from lightapi.filters import BaseFilter


def _memory_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _basic_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


class TestB1001DictConfigUnknownAuth:
    """B1-001: an `auth:` value the dict config does not know was dropped and the
    endpoint served without a backend; it is a ConfigurationError naming it."""

    def test_unknown_auth_kind_is_refused(self):
        document = {
            "endpoints": {"/things": {"fields": {"title": str}, "auth": "oauth"}}
        }

        with (
            pytest.warns(DeprecationWarning),
            pytest.raises(ConfigurationError, match="oauth"),
        ):
            LightApi.from_dict(document, engine=_memory_engine())


class TestB1011TableCreationFailureRaises:
    """B1-011: a DDL failure at build_app() was a warning and a 500 on every later
    request; it is a ConfigurationError at build_app(), with the cause attached."""

    def test_build_app_raises_when_create_all_fails(self):
        class AuditDdl(RestEndpoint):
            title: str = Field(min_length=1)

            class Meta:
                table = "audit_ddl_fails"

        app = LightApi(engine=_memory_engine())
        app.register({"/ddl": AuditDdl})
        ddl_error = OperationalError("CREATE TABLE", {}, Exception("disk full"))

        with (
            patch.object(MetaData, "create_all", side_effect=ddl_error),
            pytest.raises(ConfigurationError, match="disk full") as info,
        ):
            app.build_app()

        assert isinstance(info.value.__cause__, OperationalError)


class AuditVaried(RestEndpoint):
    label: str = Field(min_length=1)

    class Meta:
        table = "audit_varied"
        cache = Cache(ttl=60, vary_on=["page"])


class TestB6002CacheVaryOn:
    """B6-002: `Cache(vary_on=[...])` is documented as "only the listed query
    parameters contribute to the key" and was never read: the key held the whole
    query string."""

    def _keys_for(self, *paths: str) -> list[str]:
        app = LightApi(engine=_memory_engine())
        app.register({"/varied": AuditVaried})
        with patch("lightapi.cache.RedisCacheBackend.ping", return_value=True):
            client = TestClient(app.build_app())
        with (
            patch("lightapi.cache.RedisCacheBackend.get", return_value=None),
            patch("lightapi.cache.RedisCacheBackend.set") as mock_set,
        ):
            for path in paths:
                assert client.get(path).status_code == 200
        return [call.args[0] for call in mock_set.call_args_list]

    def test_unlisted_parameters_do_not_change_the_key(self):
        keys = self._keys_for(
            "/varied?page=1&q=a", "/varied?page=1&q=b", "/varied?page=1"
        )

        assert keys[0] == keys[1] == keys[2]

    def test_listed_parameter_still_changes_the_key(self):
        keys = self._keys_for("/varied?page=1", "/varied?page=2")

        assert keys[0] != keys[1]


class TestB6003ConfigJwtExpiration:
    """B6-003: `Config.jwt_expiration` existed and was never read; a backend built
    without its own `expiration` fell back to a literal 3600."""

    def test_generate_token_uses_the_global_config(self, monkeypatch):
        monkeypatch.setenv(
            "LIGHTAPI_JWT_SECRET", "audit-proposals-secret-32-bytes-long!"
        )
        monkeypatch.setattr(config, "jwt_expiration", 120)

        token = JWTAuthentication().generate_token({"sub": "1"})

        claims = jwt.decode(token, options={"verify_signature": False})
        lifetime = (
            claims["exp"] - datetime.datetime.now(datetime.timezone.utc).timestamp()
        )
        assert 100 < lifetime <= 120


class TestB7001BasicValidatorOffTheLoop:
    """B7-001: the guard called a Basic backend's validate_credentials on the event
    loop; a validator that queries a database stalled every other request."""

    def test_sync_basic_validator_runs_in_a_worker_thread(self):
        seen: dict[str, bool] = {}

        class AuditOffLoopBasic(BasicAuthentication):
            def validate_credentials(self, username, password):
                try:
                    asyncio.get_running_loop()
                    seen["on_loop"] = True
                except RuntimeError:
                    seen["on_loop"] = False
                return {"username": username}

        class AuditGuarded(RestEndpoint):
            text: str = Field(min_length=1)

            class Meta:
                table = "audit_offloop_guarded"
                authentication = Authentication(
                    backend=AuditOffLoopBasic, permission=IsAuthenticated
                )

        app = LightApi(engine=_memory_engine())
        app.register({"/guarded": AuditGuarded})
        with TestClient(app.build_app()) as client:
            response = client.get(
                "/guarded", headers={"Authorization": _basic_header("u", "p")}
            )

        assert response.status_code == 200
        assert seen["on_loop"] is False
