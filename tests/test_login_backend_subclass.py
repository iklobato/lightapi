"""/auth/login must use validate_credentials() of the backend the endpoint configured."""

import os

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import (
    Authentication,
    BasicAuthentication,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    RestEndpoint,
)
from lightapi.fields import Field as LField

SECRET = "subclass-login-secret"
EXPIRATION_SECONDS = 120


class SyncCredentialsBackend(JWTAuthentication):
    def validate_credentials(self, username: str, password: str):
        if password == "right":
            return {"sub": username, "is_admin": False}
        return None


class DirectoryBasicBackend(BasicAuthentication):
    """A subclass of BasicAuthentication with its own validate_credentials,
    matching how the README shows subclassing JWTAuthentication."""

    def validate_credentials(self, username: str, password: str):
        if password == "right":
            return {"sub": username}
        return None


class AsyncCredentialsBackend(JWTAuthentication):
    async def validate_credentials(self, username: str, password: str):
        if password == "right":
            return {"sub": username, "is_admin": True}
        return None


class OwnConstructorBackend(JWTAuthentication):
    def __init__(self) -> None:
        super().__init__(expiration=EXPIRATION_SECONDS)


class SyncBackendNote(RestEndpoint):
    text: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(
            backend=SyncCredentialsBackend,
            permission=IsAuthenticated,
            jwt_expiration=EXPIRATION_SECONDS,
        )


class AsyncBackendNote(RestEndpoint):
    text: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(
            backend=AsyncCredentialsBackend, permission=IsAuthenticated
        )


class OwnConstructorNote(RestEndpoint):
    text: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(
            backend=OwnConstructorBackend, permission=IsAuthenticated
        )


class DirectoryBasicNote(RestEndpoint):
    text: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(
            backend=DirectoryBasicBackend, permission=IsAuthenticated
        )


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setitem(os.environ, "LIGHTAPI_JWT_SECRET", SECRET)


def _client(route: str, endpoint: type, **app_kwargs) -> TestClient:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine, **app_kwargs)
    app.register({route: endpoint})
    return TestClient(app.build_app())


def test_login_uses_the_subclass_validate_credentials():
    client = _client("/syncbackendnotes", SyncBackendNote)

    response = client.post("/auth/login", json={"username": "ana", "password": "right"})

    assert response.status_code == 200
    claims = jwt.decode(response.json()["token"], SECRET, algorithms=["HS256"])
    assert claims["sub"] == "ana"
    assert response.json()["user"] == {"sub": "ana", "is_admin": False}


def test_login_with_wrong_password_on_subclass_backend_returns_401():
    client = _client("/syncbackendnotes", SyncBackendNote)

    response = client.post("/auth/login", json={"username": "ana", "password": "wrong"})

    assert response.status_code == 401


def test_login_token_lifetime_comes_from_the_endpoint_config():
    client = _client("/syncbackendnotes", SyncBackendNote)

    response = client.post("/auth/login", json={"username": "ana", "password": "right"})

    claims = jwt.decode(response.json()["token"], SECRET, algorithms=["HS256"])
    issued_for = claims["exp"] - _now()
    assert EXPIRATION_SECONDS - 5 <= issued_for <= EXPIRATION_SECONDS


def test_login_awaits_an_async_validate_credentials():
    client = _client("/asyncbackendnotes", AsyncBackendNote)

    response = client.post("/auth/login", json={"username": "bia", "password": "right"})

    assert response.status_code == 200
    assert response.json()["user"] == {"sub": "bia", "is_admin": True}


def test_app_login_validator_wins_over_the_subclass_override():
    def validator(username: str, password: str):
        return {"sub": "from-login-validator"}

    client = _client("/syncbackendnotes", SyncBackendNote, login_validator=validator)

    response = client.post("/auth/login", json={"username": "ana", "password": "wrong"})

    assert response.status_code == 200
    assert response.json()["user"] == {"sub": "from-login-validator"}


def test_backend_with_its_own_constructor_still_protects_the_endpoint():
    client = _client("/ownconstructornotes", OwnConstructorNote)
    token = OwnConstructorBackend().generate_token({"sub": "carla"})

    allowed = client.get(
        "/ownconstructornotes", headers={"Authorization": f"Bearer {token}"}
    )
    denied = client.get("/ownconstructornotes")

    assert allowed.status_code == 200
    assert denied.status_code == 401


def test_login_uses_a_basic_authentication_subclass():
    client = _client("/directorybasicnotes", DirectoryBasicNote)

    response = client.post(
        "/auth/login", json={"username": "dora", "password": "right"}
    )

    assert response.status_code == 200
    assert response.json() == {"user": {"sub": "dora"}}  # Basic: user, no token
    assert "token" not in response.json()


def test_login_with_wrong_password_on_basic_subclass_returns_401():
    client = _client("/directorybasicnotes", DirectoryBasicNote)

    response = client.post(
        "/auth/login", json={"username": "dora", "password": "wrong"}
    )

    assert response.status_code == 401


def test_basic_subclass_backend_still_guards_the_endpoint():
    import base64

    client = _client("/directorybasicnotes", DirectoryBasicNote)
    header = "Basic " + base64.b64encode(b"dora:right").decode()

    allowed = client.get("/directorybasicnotes", headers={"Authorization": header})
    denied = client.get("/directorybasicnotes")

    assert allowed.status_code == 200
    assert denied.status_code == 401


def _now() -> float:
    import time

    return time.time()
