"""Test for EndpointRateLimitMiddleware"""

import pytest
from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from lightapi import EndpointRateLimitMiddleware, HttpMethod, LightApi, RestEndpoint
from lightapi.fields import Field


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture(autouse=True)
def _reset_rate_limit_storage():
    EndpointRateLimitMiddleware.reset()
    yield
    EndpointRateLimitMiddleware.reset()


class LimitedEndpoint(RestEndpoint, HttpMethod.GET):
    """Endpoint with a 3-requests-per-minute rate limit."""

    title: str = Field(min_length=1)

    class Meta:
        rate_limit = {"requests": 3, "window": 60}


class UnlimitedEndpoint(RestEndpoint, HttpMethod.GET):
    """Endpoint without rate limiting."""

    name: str = Field(min_length=1)


@pytest.fixture
def limited_client():
    engine = _make_engine()
    app = LightApi(engine=engine, middlewares=[EndpointRateLimitMiddleware])
    app.register({"/books": LimitedEndpoint})
    return TestClient(app.build_app())


@pytest.fixture
def mixed_client():
    engine = _make_engine()
    app = LightApi(engine=engine, middlewares=[EndpointRateLimitMiddleware])
    app.register({"/books": LimitedEndpoint, "/authors": UnlimitedEndpoint})
    return TestClient(app.build_app())


class TestRateLimitHeaders:
    def test_includes_rate_limit_headers(self, limited_client):
        response = limited_client.get("/books")
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "3"
        assert response.headers["X-RateLimit-Remaining"] == "2"
        assert int(response.headers["X-RateLimit-Reset"]) <= 60


class TestRateLimitEnforcement:
    def test_requests_within_limit_succeed(self, limited_client):
        for _ in range(3):
            response = limited_client.get("/books")
            assert response.status_code == 200

    def test_request_over_limit_returns_429(self, limited_client):
        for _ in range(3):
            limited_client.get("/books")

        response = limited_client.get("/books")
        assert response.status_code == 429
        assert response.headers["X-RateLimit-Limit"] == "3"
        assert response.headers["X-RateLimit-Remaining"] == "0"
        assert int(response.headers["X-RateLimit-Reset"]) <= 60
        assert response.json()["detail"] == "Rate limit exceeded. Try again later."


class TestUnlimitedEndpoint:
    def test_unlimited_endpoint_not_blocked(self, mixed_client):
        for _ in range(3):
            mixed_client.get("/books")
        assert mixed_client.get("/books").status_code == 429

        response = mixed_client.get("/authors")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response.headers
