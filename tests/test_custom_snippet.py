import jwt
from datetime import datetime, timedelta
from starlette.testclient import TestClient

from examples.custom_snippet import create_app
from lightapi.config import config


class DummyRedis:
    def __init__(self, *args, **kwargs):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, timeout, value):
        self.store[key] = value
        return True


def get_token():
    payload = {"user": "test", "exp": datetime.utcnow() + timedelta(hours=1)}
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


def test_custom_snippet_workflow(monkeypatch):
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

        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}

        # POST request should succeed
        resp = client.post("/custom", headers=headers, json={"foo": "bar"})
        assert resp.status_code == 200
        assert resp.json()["data"] == "ok"

        # First GET populates cache
        resp1 = client.get("/custom", headers=headers)
        assert resp1.status_code == 200
        # Second GET should also succeed and return cached response
        resp2 = client.get("/custom", headers=headers)
        assert resp2.status_code == 200

