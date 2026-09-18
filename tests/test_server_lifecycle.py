"""T4-05, T4-06, T4-07: debug mode, both CORS paths, and the login rate limit."""

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import Authentication, JWTAuthentication, LightApi, RestEndpoint
from lightapi.core import CORSMiddleware
from lightapi.fields import Field
from lightapi.rate_limiter import RateLimiter


def _memory_engine():
    return create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )


class BoomEndpoint(RestEndpoint):
    name: str = Field(min_length=1)

    def get(self, request):
        raise RuntimeError("boom")


class T405Item(RestEndpoint):
    name: str = Field(min_length=1)


def test_debug_true_returns_a_traceback_page():
    app = LightApi(engine=_memory_engine())
    app.register({"/t405boom": BoomEndpoint})
    client = TestClient(app.build_app(debug=True), raise_server_exceptions=False)

    response = client.get("/t405boom")

    assert response.status_code == 500
    assert "RuntimeError" in response.text
    assert "boom" in response.text


def test_debug_false_returns_a_plain_500():
    app = LightApi(engine=_memory_engine())
    app.register({"/t405boom2": BoomEndpoint})
    client = TestClient(app.build_app(debug=False), raise_server_exceptions=False)

    response = client.get("/t405boom2")

    assert response.status_code == 500
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text


class T406Cors(RestEndpoint):
    name: str = Field(min_length=1)


def test_cors_via_constructor_option():
    app = LightApi(engine=_memory_engine(), cors_origins=["https://app.example.com"])
    app.register({"/t406a": T406Cors})
    client = TestClient(app.build_app())

    preflight = client.options(
        "/t406a",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    normal = client.get("/t406a", headers={"Origin": "https://app.example.com"})

    assert preflight.headers["access-control-allow-origin"] == "https://app.example.com"
    assert normal.headers["access-control-allow-origin"] == "https://app.example.com"


class T406Own(RestEndpoint):
    name: str = Field(min_length=1)


def test_cors_via_own_core_middleware_adds_headers_to_allowed_methods():
    """lightapi.core.CORSMiddleware runs inside EndpointHandler, which Starlette
    only reaches for the endpoint's allowed verbs. Its own OPTIONS branch is
    documented nowhere and is unreachable this way: OPTIONS is not in the
    Route's methods, so Starlette's router answers 405 before any middleware
    on the endpoint runs (this is the mechanism the docs use for cors_origins
    instead: it wraps the whole ASGI app, outside routing)."""
    app = LightApi(engine=_memory_engine(), middlewares=[CORSMiddleware])
    app.register({"/t406b": T406Own})
    client = TestClient(app.build_app())

    preflight = client.options(
        "/t406b",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    normal = client.post("/t406b", json={"name": "x"})

    assert preflight.status_code == 405
    assert normal.headers["access-control-allow-origin"] == "*"


class T407Secret(RestEndpoint):
    text: str = Field(min_length=1)

    class Meta:
        authentication = Authentication(JWTAuthentication)


def test_login_rate_limit_returns_429_with_headers(monkeypatch):
    monkeypatch.setenv("LIGHTAPI_JWT_SECRET", "t407-secret")

    def validator(username, password):
        return {"sub": username} if password == "right" else None

    app = LightApi(
        engine=_memory_engine(),
        login_validator=validator,
        rate_limiter=RateLimiter(requests_per_minute=3),
    )
    app.register({"/t407secrets": T407Secret})
    client = TestClient(app.build_app())
    body = {"username": "a", "password": "right"}

    responses = [client.post("/auth/login", json=body) for _ in range(4)]

    assert [r.status_code for r in responses] == [200, 200, 200, 429]
    limited = responses[-1]
    assert "detail" in limited.json()
    assert limited.headers.get("retry-after") is not None


def test_default_rate_limit_is_generous_for_normal_use(monkeypatch):
    monkeypatch.setenv("LIGHTAPI_JWT_SECRET", "t407-defaults-secret")

    def validator(username, password):
        return {"sub": username}

    app = LightApi(engine=_memory_engine(), login_validator=validator)
    app.register({"/t407defaults": T407Secret})
    client = TestClient(app.build_app())

    responses = [
        client.post("/auth/login", json={"username": "a", "password": "x"})
        for _ in range(5)
    ]

    assert all(r.status_code == 200 for r in responses)
