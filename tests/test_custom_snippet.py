import json
from datetime import datetime, timedelta, timezone

import jwt
from starlette.testclient import TestClient

from examples.middleware_cors_auth import Company, CustomEndpoint, create_app
from lightapi.config import config
from lightapi.lightapi import LightApi
from lightapi.core import Middleware, Response


class DummyRedis:
    def __init__(self, *args, **kwargs):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, timeout, value):
        self.store[key] = value
        return True

    def set(self, key, value, **kwargs):
        """Support for set method with optional timeout"""
        self.store[key] = value
        return True


def get_token():
    payload = {"user": "test", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


def test_cors_middleware(monkeypatch):
    """Test CORS middleware functionality"""
    monkeypatch.setattr("redis.Redis", DummyRedis)

    app = create_app()
    from starlette.applications import Starlette

    if not hasattr(app, 'starlette_routes'):
        app.starlette_routes = []
    starlette_app = Starlette(routes=app.starlette_routes)

    with TestClient(starlette_app) as client:
        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Test OPTIONS request
        resp = client.options("/customendpoint", headers=headers)
        assert resp.status_code == 200

        # Test CORS headers on regular request
        resp = client.get("/customendpoint", headers=headers)
        assert resp.headers["Access-Control-Allow-Origin"] == "*"
        assert "GET" in resp.headers["Access-Control-Allow-Methods"]
        assert "POST" in resp.headers["Access-Control-Allow-Methods"]
        assert "Authorization" in resp.headers["Access-Control-Allow-Headers"]
        assert "Content-Type" in resp.headers["Access-Control-Allow-Headers"]


def test_company_endpoint_functionality():
    """Test Company endpoint with validation and filtering"""
    app = LightApi()
    app.register(Company)

    from starlette.applications import Starlette

    if not hasattr(app, 'starlette_routes'):
        app.starlette_routes = []
    starlette_app = Starlette(routes=app.starlette_routes)

    with TestClient(starlette_app) as client:
        # Test GET request
        resp = client.get("/company")
        assert resp.status_code == 200
        assert resp.json()["data"] == "ok"

        # Test POST request with data
        test_data = {
            "name": "Test Company",
            "email": "test@company.com",
            "website": "https://testcompany.com",
        }
        resp = client.post("/company", json=test_data)
        assert resp.status_code == 200
        response_data = resp.json()
        assert response_data["status"] == "ok"
        assert "data" in response_data


def test_request_data_handling(monkeypatch):
    """Test handling of request data"""
    monkeypatch.setattr("redis.Redis", DummyRedis)

    app = create_app()
    from starlette.applications import Starlette

    if not hasattr(app, 'starlette_routes'):
        app.starlette_routes = []
    starlette_app = Starlette(routes=app.starlette_routes)

    with TestClient(starlette_app) as client:
        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Test POST with various data types
        test_cases = [
            {"simple": "data"},
            {"nested": {"key": "value"}},
            {"array": [1, 2, 3]},
            {"mixed": {"string": "test", "number": 42, "array": [1, 2]}},
        ]

        for test_data in test_cases:
            resp = client.post("/customendpoint", headers=headers, json=test_data)
            assert resp.status_code == 200
            assert resp.json()["data"] == "ok"


def test_http_methods_configuration():
    """Test that only configured HTTP methods are allowed"""
    app = LightApi()
    app.register(Company)

    from starlette.applications import Starlette

    if not hasattr(app, 'starlette_routes'):
        app.starlette_routes = []
    starlette_app = Starlette(routes=app.starlette_routes)

    with TestClient(starlette_app) as client:
        # Company endpoint should support GET and POST
        resp = client.get("/company")
        assert resp.status_code == 200

        resp = client.post("/company", json={"name": "test"})
        assert resp.status_code == 200

        # PUT, DELETE should not be allowed (405 Method Not Allowed or similar)
        resp = client.put("/company", json={"name": "test"})
        assert resp.status_code in [405, 404]

        resp = client.delete("/company")
        assert resp.status_code in [405, 404]


def test_pagination_configuration(monkeypatch):
    """Test custom pagination configuration"""
    monkeypatch.setattr("redis.Redis", DummyRedis)

    # This test verifies that CustomPaginator is configured
    # The actual pagination logic would be tested in integration scenarios
    app = create_app()
    from starlette.applications import Starlette

    if not hasattr(app, 'starlette_routes'):
        app.starlette_routes = []
    starlette_app = Starlette(routes=app.starlette_routes)

    with TestClient(starlette_app) as client:
        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Basic request should work with pagination configured
        resp = client.get("/customendpoint", headers=headers)
        assert resp.status_code == 200

        # Test with pagination parameters
        resp = client.get("/customendpoint?limit=10&offset=0", headers=headers)
        assert resp.status_code == 200
