"""Tests for US7: Middleware processing chain."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
from lightapi.core import Middleware
from lightapi.fields import Field as LField


class AuditEndpoint(RestEndpoint):
    message: str = LField(min_length=1)


class LoggingMiddleware(Middleware):
    calls: list = []

    def process(self, request: Request, response: Response | None) -> Response | None:
        LoggingMiddleware.calls.append(
            ("pre" if response is None else "post", request.method)
        )
        return None if response is None else response


class ShortCircuitMiddleware(Middleware):
    def process(self, request: Request, response: Response | None) -> Response | None:
        if response is None and request.headers.get("X-Block") == "true":
            return JSONResponse({"detail": "blocked by middleware"}, status_code=403)
        return response


@pytest.fixture(scope="module")
def client_with_logging():
    LoggingMiddleware.calls = []
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app_instance = LightApi(engine=engine, middlewares=[LoggingMiddleware])
    app_instance.register({"/audit": AuditEndpoint})
    return TestClient(app_instance.build_app())


@pytest.fixture(scope="module")
def client_with_block():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app_instance = LightApi(engine=engine, middlewares=[ShortCircuitMiddleware])
    app_instance.register({"/guarded": AuditEndpoint})
    return TestClient(app_instance.build_app())


class TestMiddlewareInvoked:
    def test_pre_middleware_called_on_get(self, client_with_logging):
        LoggingMiddleware.calls.clear()
        client_with_logging.get("/audit")
        assert any(phase == "pre" and method == "GET" for phase, method in LoggingMiddleware.calls)

    def test_post_middleware_called_after_get(self, client_with_logging):
        LoggingMiddleware.calls.clear()
        client_with_logging.get("/audit")
        assert any(phase == "post" for phase, _ in LoggingMiddleware.calls)


class TestShortCircuit:
    def test_blocked_request_returns_403(self, client_with_block):
        resp = client_with_block.get("/guarded", headers={"X-Block": "true"})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "blocked by middleware"

    def test_normal_request_passes_through(self, client_with_block):
        resp = client_with_block.get("/guarded")
        assert resp.status_code == 200
