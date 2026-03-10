"""Tests for login and token endpoints (US-L1, US-L2, US-L3, US-L4)."""

import base64
import os

import jwt
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import (
    Authentication,
    BasicAuthentication,
    JWTAuthentication,
    LightApi,
    RestEndpoint,
)
from lightapi._login import LoginRequest
from lightapi.exceptions import ConfigurationError
from lightapi.fields import Field as LField


def _valid_validator(username: str, password: str):
    if username == "alice" and password == "secret":
        return {"sub": "1", "email": "alice@example.com", "is_admin": False}
    return None


def _valid_validator_admin(username: str, password: str):
    if username == "admin" and password == "admin":
        return {"sub": "2", "is_admin": True}
    return None


class JWTProtectedEndpoint(RestEndpoint):
    content: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(backend=JWTAuthentication)


class BasicProtectedEndpoint(RestEndpoint):
    name: str = LField(min_length=1)

    class Meta:
        authentication = Authentication(backend=BasicAuthentication)


@pytest.fixture(scope="module")
def jwt_client():
    os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine, login_validator=_valid_validator)
    app.register({"/secrets": JWTProtectedEndpoint})
    return TestClient(app.build_app())


@pytest.fixture(scope="module")
def basic_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine, login_validator=_valid_validator)
    app.register({"/items": BasicProtectedEndpoint})
    return TestClient(app.build_app())


class TestJWTTokenEndpoint:
    def test_login_valid_credentials_returns_token(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["sub"] == "1"
        assert data["user"]["email"] == "alice@example.com"

    def test_login_invalid_credentials_returns_401(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            json={"username": "alice", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_login_missing_body_returns_422(self, jwt_client):
        resp = jwt_client.post("/auth/login", json={})
        assert resp.status_code == 422

    def test_token_endpoint_same_as_login(self, jwt_client):
        resp = jwt_client.post(
            "/auth/token",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        assert "token" in resp.json()
        assert "user" in resp.json()


class TestBodyValidation:
    def test_login_missing_username_returns_422(self, jwt_client):
        resp = jwt_client.post("/auth/login", json={"password": "x"})
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("username" in str(e.get("loc", [])) for e in detail)

    def test_login_missing_password_returns_422(self, jwt_client):
        resp = jwt_client.post("/auth/login", json={"username": "x"})
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("password" in str(e.get("loc", [])) for e in detail)

    def test_login_empty_username_returns_422(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            json={"username": "", "password": "x"},
        )
        assert resp.status_code == 422

    def test_login_empty_password_returns_422(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            json={"username": "x", "password": ""},
        )
        assert resp.status_code == 422

    def test_login_invalid_json_returns_422(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


class TestBasicHeaderInput:
    def test_login_basic_header_valid_returns_token(self, jwt_client):
        creds = base64.b64encode(b"alice:secret").decode()
        resp = jwt_client.post(
            "/auth/login",
            headers={"Authorization": f"Basic {creds}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["sub"] == "1"

    def test_login_basic_header_takes_precedence_over_body(self, jwt_client):
        creds = base64.b64encode(b"alice:secret").decode()
        resp = jwt_client.post(
            "/auth/login",
            headers={"Authorization": f"Basic {creds}"},
            json={"username": "alice", "password": "wrong"},
        )
        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_login_basic_header_malformed_returns_401(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            headers={"Authorization": "Basic not-valid-base64!!"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_login_basic_header_no_colon_returns_401(self, jwt_client):
        creds = base64.b64encode(b"nocolon").decode()
        resp = jwt_client.post(
            "/auth/login",
            headers={"Authorization": f"Basic {creds}"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_login_bearer_header_falls_through_to_body_validation(self, jwt_client):
        """Authorization: Bearer x (no Basic) + empty body → 422."""
        resp = jwt_client.post(
            "/auth/login",
            headers={"Authorization": "Bearer x"},
            json={},
        )
        assert resp.status_code == 422


class TestBasicAuthEndpoint:
    def test_basic_only_returns_user_without_token(self, basic_client):
        resp = basic_client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert "token" not in data
        assert data["user"]["sub"] == "1"


class TestHttpMethodAndErrorFormat:
    def test_login_get_returns_405(self, jwt_client):
        resp = jwt_client.get("/auth/login")
        assert resp.status_code == 405
        assert resp.headers.get("Allow") == "POST"


class TestConfigurationAndRegistration:
    def test_register_jwt_without_validator_raises_configuration_error(self):
        os.environ.setdefault("LIGHTAPI_JWT_SECRET", "test-secret-key")
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine)
        with pytest.raises(ConfigurationError, match="login_validator"):
            app.register({"/secrets": JWTProtectedEndpoint})

    def test_register_basic_without_validator_raises_configuration_error(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine)
        with pytest.raises(ConfigurationError, match="login_validator"):
            app.register({"/items": BasicProtectedEndpoint})

    def test_auth_path_customization(self):
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(
            engine=engine,
            login_validator=_valid_validator,
            auth_path="/api/auth",
        )
        app.register({"/secrets": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        assert "token" in resp.json()


class TestJWTConfigOverrides:
    def test_jwt_expiration_override(self):
        class JWTWithExpEndpoint(RestEndpoint):
            content: str = LField(min_length=1)

            class Meta:
                authentication = Authentication(
                    backend=JWTAuthentication,
                    jwt_expiration=10,
                )

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=_valid_validator)
        app.register({"/x": JWTWithExpEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        exp = payload.get("exp")
        assert exp is not None
        import time

        assert 0 < exp - int(time.time()) <= 15

    def test_jwt_extra_claims_filters_payload(self):
        def validator_with_extra(username: str, password: str):
            if username == "alice" and password == "secret":
                return {
                    "sub": "1",
                    "email": "a@b.com",
                    "secret": "must-not-appear",
                }
            return None

        class JWTWithExtraEndpoint(RestEndpoint):
            content: str = LField(min_length=1)

            class Meta:
                authentication = Authentication(
                    backend=JWTAuthentication,
                    jwt_extra_claims=["sub", "email"],
                )

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=validator_with_extra)
        app.register({"/x": JWTWithExtraEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert "sub" in payload
        assert "email" in payload
        assert "secret" not in payload


class TestBasicAuthProtectedEndpoints:
    def test_basic_protected_get_with_valid_header_returns_200(self, basic_client):
        creds = base64.b64encode(b"alice:secret").decode()
        resp = basic_client.get(
            "/items",
            headers={"Authorization": f"Basic {creds}"},
        )
        assert resp.status_code == 200

    def test_basic_protected_get_without_auth_returns_401(self, basic_client):
        resp = basic_client.get("/items")
        assert resp.status_code == 401

    def test_basic_protected_get_invalid_credentials_returns_401(self, basic_client):
        creds = base64.b64encode(b"alice:wrong").decode()
        resp = basic_client.get(
            "/items",
            headers={"Authorization": f"Basic {creds}"},
        )
        assert resp.status_code == 401


class TestTokenUsability:
    def test_jwt_token_usable_on_protected_endpoint(self, jwt_client):
        login_resp = jwt_client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]
        resp = jwt_client.get(
            "/secrets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestValidatorException:
    def test_login_validator_exception_returns_500(self):
        """Validator raising propagates to 500 (Starlette default handler)."""

        def failing_validator(username: str, password: str):
            raise RuntimeError("DB unavailable")

        os.environ.setdefault("LIGHTAPI_JWT_SECRET", "test-secret-key")
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=failing_validator)
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app(), raise_server_exceptions=False)
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 500


class TestLoginRequestModel:
    def test_login_request_validates_min_length(self):
        with pytest.raises(ValidationError):
            LoginRequest.model_validate({"username": "x", "password": ""})


class TestBasicHeaderEdgeCases:
    def test_login_basic_header_password_with_colon_parsed_correctly(self):
        def validator_colon(username: str, password: str):
            if username == "alice" and password == "pass:word":
                return {"sub": "1"}
            return None

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=validator_colon)
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        creds = base64.b64encode(b"alice:pass:word").decode()
        resp = client.post(
            "/auth/login",
            headers={"Authorization": f"Basic {creds}"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["sub"] == "1"

    def test_login_basic_header_empty_username_returns_401(self):
        def validator_reject_empty(username: str, password: str):
            if not username or not password:
                return None
            if username == "alice" and password == "secret":
                return {"sub": "1"}
            return None

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=validator_reject_empty)
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        creds = base64.b64encode(b":secret").decode()
        resp = client.post(
            "/auth/login",
            headers={"Authorization": f"Basic {creds}"},
        )
        assert resp.status_code == 401

    def test_login_basic_header_empty_password_returns_401(self):
        def validator_reject_empty(username: str, password: str):
            if not username or not password:
                return None
            if username == "alice" and password == "secret":
                return {"sub": "1"}
            return None

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=validator_reject_empty)
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        creds = base64.b64encode(b"alice:").decode()
        resp = client.post(
            "/auth/login",
            headers={"Authorization": f"Basic {creds}"},
        )
        assert resp.status_code == 401

    def test_login_basic_header_unicode_credentials_success(self):
        def validator_unicode(username: str, password: str):
            if username == "josé" and password == "contraseña":
                return {"sub": "1"}
            return None

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=validator_unicode)
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        creds = base64.b64encode("josé:contraseña".encode("utf-8")).decode()
        resp = client.post(
            "/auth/login",
            headers={"Authorization": f"Basic {creds}"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["sub"] == "1"

    def test_login_basic_header_lowercase_falls_through_to_body(self):
        """Authorization: basic x (lowercase) does not match Basic; falls to body."""
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=_valid_validator)
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        creds = base64.b64encode(b"alice:secret").decode()
        resp = client.post(
            "/auth/login",
            headers={"Authorization": f"basic {creds}"},
            json={},
        )
        assert resp.status_code == 422

    def test_login_basic_header_no_value_returns_401(self):
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=_valid_validator)
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            headers={"Authorization": "Basic "},
            json={},
        )
        assert resp.status_code == 401

    def test_login_basic_header_multiple_spaces_after_basic(self):
        """Authorization: Basic  <space><base64> - leading space may affect decode."""
        creds = base64.b64encode(b"alice:secret").decode()
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=_valid_validator)
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            headers={"Authorization": f"Basic  {creds}"},
        )
        assert resp.status_code in (200, 401)
        if resp.status_code == 200:
            assert resp.json()["user"]["sub"] == "1"


class TestBodyEdgeCases:
    def test_login_body_with_extra_keys_ignored_success(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret", "extra": "x"},
        )
        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_login_body_wrong_type_username_returns_422(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            json={"username": 123, "password": "x"},
        )
        assert resp.status_code == 422

    def test_login_truncated_json_returns_422(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            content='{"username": "a",',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_login_empty_body_with_content_type_returns_422(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            content="{}",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


class TestAuthPathEdgeCases:
    def test_auth_path_trailing_slash_normalized(self):
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(
            engine=engine,
            login_validator=_valid_validator,
            auth_path="/auth/",
        )
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_auth_path_root_routes_at_login_and_token(self):
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(
            engine=engine,
            login_validator=_valid_validator,
            auth_path="/",
        )
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_auth_path_nested(self):
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(
            engine=engine,
            login_validator=_valid_validator,
            auth_path="/api/v1/auth",
        )
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        assert "token" in resp.json()


class TestJWTExtraClaimsEdgeCases:
    def test_jwt_extra_claims_empty_list_uses_full_payload(self):
        def validator_full(username: str, password: str):
            if username == "alice" and password == "secret":
                return {"sub": "1", "email": "a@b.com"}
            return None

        class JWTEmptyExtraEndpoint(RestEndpoint):
            content: str = LField(min_length=1)

            class Meta:
                authentication = Authentication(
                    backend=JWTAuthentication,
                    jwt_extra_claims=[],
                )

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=validator_full)
        app.register({"/x": JWTEmptyExtraEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert "sub" in payload
        assert "email" in payload

    def test_jwt_extra_claims_all_keys_missing_fallback_to_full_payload(self):
        def validator_minimal(username: str, password: str):
            if username == "alice" and password == "secret":
                return {"sub": "1"}
            return None

        class JWTMissingExtraEndpoint(RestEndpoint):
            content: str = LField(min_length=1)

            class Meta:
                authentication = Authentication(
                    backend=JWTAuthentication,
                    jwt_extra_claims=["x", "y"],
                )

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=validator_minimal)
        app.register({"/x": JWTMissingExtraEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert "sub" in payload

    def test_jwt_extra_claims_partial_overlap_only_included_in_token(self):
        def validator_partial(username: str, password: str):
            if username == "alice" and password == "secret":
                return {"sub": "1", "email": "a@b.com"}
            return None

        class JWTPartialExtraEndpoint(RestEndpoint):
            content: str = LField(min_length=1)

            class Meta:
                authentication = Authentication(
                    backend=JWTAuthentication,
                    jwt_extra_claims=["sub", "missing"],
                )

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=validator_partial)
        app.register({"/x": JWTPartialExtraEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert "sub" in payload
        assert payload["sub"] == "1"
        assert "missing" not in payload


class TestValidatorReturnShapes:
    def test_validator_empty_dict_returns_200(self):
        def validator_empty(username: str, password: str):
            if username == "alice" and password == "secret":
                return {}
            return None

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=validator_empty)
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"] == {}
        token = data["token"]
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert "exp" in payload

    def test_validator_nested_payload_success(self):
        def validator_nested(username: str, password: str):
            if username == "alice" and password == "secret":
                return {"sub": "1", "meta": {"role": "admin"}}
            return None

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=validator_nested)
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["sub"] == "1"
        assert data["user"]["meta"]["role"] == "admin"


class TestMixedAppScenarios:
    def test_both_jwt_and_basic_endpoints_returns_token(self):
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=_valid_validator)
        app.register(
            {
                "/secrets": JWTProtectedEndpoint,
                "/items": BasicProtectedEndpoint,
            }
        )
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_basic_only_auth_token_same_as_login(self, basic_client):
        resp = basic_client.post(
            "/auth/token",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert "token" not in data

    def test_allowany_only_no_auth_routes_404(self):
        from lightapi import AllowAny

        class AllowAnyEndpoint(RestEndpoint):
            name: str = LField(min_length=1)

            class Meta:
                authentication = Authentication(backend=AllowAny)

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=_valid_validator)
        app.register({"/public": AllowAnyEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 404


class TestMethodEdgeCases:
    def test_put_auth_login_returns_405(self, jwt_client):
        resp = jwt_client.put(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 405
        assert resp.headers.get("Allow") == "POST"

    def test_patch_auth_token_returns_405(self, jwt_client):
        resp = jwt_client.patch(
            "/auth/token",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 405
        assert resp.headers.get("Allow") == "POST"

    def test_delete_auth_login_returns_405(self, jwt_client):
        resp = jwt_client.delete("/auth/login")
        assert resp.status_code == 405
        assert resp.headers.get("Allow") == "POST"


class TestResponseStructure:
    def test_jwt_mode_response_has_exactly_token_and_user(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"token", "user"}

    def test_basic_mode_response_has_no_token_key(self, basic_client):
        resp = basic_client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        assert "token" not in resp.json()
        assert "user" in resp.json()


class TestTokenVerification:
    def test_expired_token_rejected_on_protected_endpoint(self):
        import time

        class JWTExpiringEndpoint(RestEndpoint):
            content: str = LField(min_length=1)

            class Meta:
                authentication = Authentication(
                    backend=JWTAuthentication,
                    jwt_expiration=1,
                )

        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=_valid_validator)
        app.register({"/x": JWTExpiringEndpoint})
        client = TestClient(app.build_app())
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        time.sleep(2)
        get_resp = client.get("/x", headers={"Authorization": f"Bearer {token}"})
        assert get_resp.status_code == 401

    def test_wrong_secret_token_rejected(self):
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key"
        wrong_token = jwt.encode(
            {"sub": "1", "exp": 9999999999},
            "wrong-secret",
            algorithm="HS256",
        )
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine, login_validator=_valid_validator)
        app.register({"/x": JWTProtectedEndpoint})
        client = TestClient(app.build_app())
        resp = client.get(
            "/x",
            headers={"Authorization": f"Bearer {wrong_token}"},
        )
        assert resp.status_code == 401

    def test_token_structure_has_three_parts(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        assert len(token.split(".")) == 3


class TestBasicVsBodyPrecedence:
    def test_malformed_basic_overrides_valid_body_returns_401(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            headers={"Authorization": "Basic not-valid-base64!!"},
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 401

    def test_invalid_basic_and_empty_body_returns_401(self, jwt_client):
        resp = jwt_client.post(
            "/auth/login",
            headers={"Authorization": "Basic !!!"},
            json={},
        )
        assert resp.status_code == 401
