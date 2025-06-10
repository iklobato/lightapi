import json
from datetime import datetime, timedelta, timezone

import jwt
from starlette.testclient import TestClient

from examples.custom_snippet import Company, CustomEndpoint, create_app
from lightapi.config import config
from lightapi.core import LightApi


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


def test_custom_snippet_workflow(monkeypatch):
    """Test basic custom snippet workflow with auth and caching"""
    # Patch redis.Redis used by RedisCache
    monkeypatch.setattr("redis.Redis", DummyRedis)

    app = create_app()

    # Create starlette application manually
    from starlette.applications import Starlette

    starlette_app = Starlette(routes=app.routes)

    with TestClient(starlette_app) as client:
        # Missing auth should return 403 via middleware
        resp = client.get("/custom")
        assert resp.status_code == 403
        assert resp.json()["error"] == "not allowed"

        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}

        # POST request should succeed
        resp = client.post("/custom", headers=headers, json={"foo": "bar"})
        assert resp.status_code == 200
        assert resp.json()["data"] == "ok"

        # First GET populates cache
        resp1 = client.get("/custom", headers=headers)
        assert resp1.status_code == 200
        assert resp1.json()["data"] == "ok"

        # Second GET should also succeed and return cached response
        resp2 = client.get("/custom", headers=headers)
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()


def test_cors_middleware(monkeypatch):
    """Test CORS middleware functionality"""
    monkeypatch.setattr("redis.Redis", DummyRedis)

    app = create_app()
    from starlette.applications import Starlette

    starlette_app = Starlette(routes=app.routes)

    with TestClient(starlette_app) as client:
        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Test OPTIONS request
        resp = client.options("/custom", headers=headers)
        assert resp.status_code == 200

        # Test CORS headers on regular request
        resp = client.get("/custom", headers=headers)
        assert resp.headers["Access-Control-Allow-Origin"] == "*"
        assert "GET" in resp.headers["Access-Control-Allow-Methods"]
        assert "POST" in resp.headers["Access-Control-Allow-Methods"]
        assert "Authorization" in resp.headers["Access-Control-Allow-Headers"]
        assert "Content-Type" in resp.headers["Access-Control-Allow-Headers"]


def test_company_endpoint_functionality():
    """Test Company endpoint with validation and filtering"""
    app = LightApi()
    app.register({"/company": Company})

    from starlette.applications import Starlette

    starlette_app = Starlette(routes=app.routes)

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


def test_authentication_edge_cases(monkeypatch):
    """Test various authentication scenarios"""
    monkeypatch.setattr("redis.Redis", DummyRedis)

    app = create_app()
    from starlette.applications import Starlette

    starlette_app = Starlette(routes=app.routes)

    with TestClient(starlette_app) as client:
        # Test with invalid token - first hit middleware
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        resp = client.get("/custom", headers=invalid_headers)
        # Authentication middleware returns 403 for invalid token
        assert resp.status_code == 403

        # Test with expired token
        expired_payload = {
            "user": "test",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            expired_payload, config.jwt_secret, algorithm="HS256"
        )
        expired_headers = {"Authorization": f"Bearer {expired_token}"}
        resp = client.get("/custom", headers=expired_headers)
        # Authentication middleware returns 403 for expired token
        assert resp.status_code == 403

        # Test with malformed Authorization header
        malformed_headers = {"Authorization": "InvalidFormat"}
        resp = client.get("/custom", headers=malformed_headers)
        # Should pass middleware since it has Authorization header, but fail JWT
        assert resp.status_code in [401, 403, 500]


def test_caching_behavior(monkeypatch):
    """Test caching behavior in detail"""

    # Create a mock redis that tracks calls
    class TrackingRedis(DummyRedis):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.get_calls = []
            self.set_calls = []
            self.setex_calls = []

        def get(self, key):
            self.get_calls.append(key)
            return super().get(key)

        def set(self, key, value, **kwargs):
            self.set_calls.append((key, value, kwargs))
            return super().set(key, value, **kwargs)

        def setex(self, key, timeout, value):
            self.setex_calls.append((key, timeout, value))
            return super().setex(key, timeout, value)

    tracking_redis = TrackingRedis()
    monkeypatch.setattr("redis.Redis", lambda *args, **kwargs: tracking_redis)

    app = create_app()
    from starlette.applications import Starlette

    starlette_app = Starlette(routes=app.routes)

    with TestClient(starlette_app) as client:
        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}

        # First GET request should miss cache and set it
        resp1 = client.get("/custom", headers=headers)
        assert resp1.status_code == 200

        # Should have made at least one get call (cache miss)
        assert len(tracking_redis.get_calls) >= 1

        # Should have made either a set call or setex call (Redis cache implementation detail)
        cache_was_set = (
            len(tracking_redis.set_calls) >= 1 or len(tracking_redis.setex_calls) >= 1
        )
        assert (
            cache_was_set
        ), f"Cache should have been set. set_calls: {tracking_redis.set_calls}, setex_calls: {tracking_redis.setex_calls}"

        # Verify timeout was set (check both set and setex calls)
        timeout_was_set = False
        for _, _, kwargs in tracking_redis.set_calls:
            if "timeout" in kwargs:
                timeout_was_set = True
                break
        for _, timeout, _ in tracking_redis.setex_calls:
            if timeout:
                timeout_was_set = True
                break
        assert timeout_was_set, "Cache timeout should have been set"

        # Second GET request should hit cache (or at least work)
        resp2 = client.get("/custom", headers=headers)
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()


def test_middleware_interaction(monkeypatch):
    """Test interaction between multiple middleware"""
    monkeypatch.setattr("redis.Redis", DummyRedis)

    app = create_app()
    from starlette.applications import Starlette

    starlette_app = Starlette(routes=app.routes)

    with TestClient(starlette_app) as client:
        token = get_token()

        # Test that both middlewares are applied in correct order
        # MyCustomMiddleware should block unauthorized requests
        resp = client.get("/custom")
        assert resp.status_code == 403
        assert resp.json()["error"] == "not allowed"

        # With auth, both middlewares should process the request
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.get("/custom", headers=headers)
        assert resp.status_code == 200
        # Should have CORS headers from CORSMiddleware
        assert resp.headers["Access-Control-Allow-Origin"] == "*"


def test_request_data_handling(monkeypatch):
    """Test handling of request data"""
    monkeypatch.setattr("redis.Redis", DummyRedis)

    app = create_app()
    from starlette.applications import Starlette

    starlette_app = Starlette(routes=app.routes)

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
            resp = client.post("/custom", headers=headers, json=test_data)
            assert resp.status_code == 200
            assert resp.json()["data"] == "ok"


def test_http_methods_configuration():
    """Test that only configured HTTP methods are allowed"""
    app = LightApi()
    app.register({"/company": Company})

    from starlette.applications import Starlette

    starlette_app = Starlette(routes=app.routes)

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

    starlette_app = Starlette(routes=app.routes)

    with TestClient(starlette_app) as client:
        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Basic request should work with pagination configured
        resp = client.get("/custom", headers=headers)
        assert resp.status_code == 200

        # Test with pagination parameters
        resp = client.get("/custom?limit=10&offset=0", headers=headers)
        assert resp.status_code == 200
