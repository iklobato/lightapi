"""Tests for US3: Authentication and Permission classes."""

import os
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import (
    Authentication,
    IsAdminUser,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    RestEndpoint,
)
from lightapi.auth import AllowAny
from lightapi.fields import Field as LField


class SecretEndpoint(RestEndpoint):
    content: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(backend=JWTAuthentication)


class AdminEndpoint(RestEndpoint):
    value: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAdminUser,
        )


class PublicEndpoint(RestEndpoint):
    name: str = LField(min_length=1)


class PerMethodAuthEndpoint(RestEndpoint):
    """GET: AllowAny, POST: IsAuthenticated."""

    name: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission={"GET": AllowAny, "POST": IsAuthenticated},
        )


@pytest.fixture(scope="module")
def jwt_secret(monkeypatch_session=None):
    secret = "test-secret-key"
    os.environ["LIGHTAPI_JWT_SECRET"] = secret
    return secret


def _login_validator(_username: str, _password: str) -> dict[str, Any] | None:
    """Test validator; always returns None (tests use _make_token for tokens)."""
    return None


@pytest.fixture(scope="module")
def client(jwt_secret):
    os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app_instance = LightApi(engine=engine, login_validator=_login_validator)
    app_instance.register(
        {
            "/secrets": SecretEndpoint,
            "/admin": AdminEndpoint,
            "/public": PublicEndpoint,
            "/permethod": PerMethodAuthEndpoint,
        }
    )
    return TestClient(app_instance.build_app())


def _make_token(payload: dict, secret: str = "test-secret-key") -> str:
    import jwt

    return jwt.encode(payload, secret, algorithm="HS256")


class TestNoAuthRequired:
    def test_public_get_no_token_200(self, client):
        resp = client.get("/public")
        assert resp.status_code == 200


class TestJWTAuth:
    def test_missing_token_returns_401(self, client):
        resp = client.get("/secrets")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        resp = client.get(
            "/secrets", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401

    def test_valid_token_allows_access(self, client):
        token = _make_token({"sub": "user1"})
        resp = client.get("/secrets", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_expired_token_returns_401(self, client):
        import time

        token = _make_token({"sub": "user1", "exp": int(time.time()) - 10})
        resp = client.get("/secrets", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


class TestIsAdminUser:
    def test_non_admin_returns_403(self, client):
        token = _make_token({"sub": "user1", "is_admin": False})
        resp = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_admin_allowed(self, client):
        token = _make_token({"sub": "admin", "is_admin": True})
        resp = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_missing_is_admin_claim_returns_403(self, client):
        token = _make_token({"sub": "user1"})
        resp = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestPermissionClasses:
    def test_allow_any_permits_all(self):
        from types import SimpleNamespace

        req = SimpleNamespace(state=SimpleNamespace(user=None))
        assert AllowAny().has_permission(req) is True

    def test_is_authenticated_requires_user(self):
        from types import SimpleNamespace

        req_no_user = SimpleNamespace(state=SimpleNamespace())
        req_with_user = SimpleNamespace(state=SimpleNamespace(user={"sub": "u1"}))
        assert IsAuthenticated().has_permission(req_no_user) is False
        assert IsAuthenticated().has_permission(req_with_user) is True

    def test_is_admin_requires_is_admin_true(self):
        from types import SimpleNamespace

        req_non_admin = SimpleNamespace(state=SimpleNamespace(user={"is_admin": False}))
        req_admin = SimpleNamespace(state=SimpleNamespace(user={"is_admin": True}))
        req_no_claim = SimpleNamespace(state=SimpleNamespace(user={"sub": "u"}))
        assert IsAdminUser().has_permission(req_non_admin) is False
        assert IsAdminUser().has_permission(req_admin) is True
        assert IsAdminUser().has_permission(req_no_claim) is False


class TestPerMethodAuth:
    """Authentication(permission={"GET": AllowAny, "POST": IsAuthenticated})."""

    def test_per_method_auth_get_allow_post_require(self, client):
        """GET with AllowAny -> 200 without token; POST with IsAuthenticated -> 401 without token."""
        resp_get = client.get("/permethod")
        assert resp_get.status_code == 200
        resp_post = client.post("/permethod", json={"name": "x"})
        assert (
            resp_post.status_code == 401
        )  # No token = auth fails before permission check
        token = _make_token({"sub": "user1"})
        resp_post_authed = client.post(
            "/permethod",
            json={"name": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_post_authed.status_code == 201
