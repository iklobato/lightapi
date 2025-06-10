import json
from unittest.mock import MagicMock

import pytest
import redis
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from lightapi.cache import RedisCache
from lightapi.core import LightApi, Middleware, Response
from lightapi.filters import ParameterFilter
from lightapi.rest import RestEndpoint


class DummyRedis:
    def __init__(self, *args, **kwargs):
        self.store = {}
        self.setex_count = 0

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, timeout, value):
        self.setex_count += 1
        self.store[key] = value
        return True


def test_response_asgi_call():
    async def endpoint(request):
        return Response({"hello": "world"})

    app = Starlette(routes=[Route("/", endpoint)])
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"hello": "world"}


def test_jwt_auth_missing_secret(monkeypatch):
    from lightapi import auth

    monkeypatch.setattr(auth.config, "jwt_secret", None)
    with pytest.raises(ValueError):
        auth.JWTAuthentication()


def test_parameter_filter_ignores_unknown():
    filter_obj = ParameterFilter()
    query = MagicMock()
    entity = type("E", (), {"name": "n"})
    query.column_descriptions = [{"entity": entity}]
    filtered = MagicMock()
    query.filter.return_value = filtered
    request = type("Req", (), {"query_params": {"name": "a", "unknown": "x"}})()

    result = filter_obj.filter_queryset(query, request)
    query.filter.assert_called_once()
    assert result == filtered


def test_middleware_execution_order():
    order = []

    class First(Middleware):
        def process(self, request, response):
            if response is None:
                order.append("pre1")
            else:
                order.append("post1")
            return response

    class Second(Middleware):
        def process(self, request, response):
            if response is None:
                order.append("pre2")
            else:
                order.append("post2")
            return response

    class EP(RestEndpoint):
        class Configuration:
            http_method_names = ["GET"]

        def get(self, request):
            return {"ok": True}, 200

    app = LightApi()
    app.register({"/ep": EP})
    app.add_middleware([First, Second])
    star = Starlette(routes=app.routes)
    with TestClient(star) as client:
        client.get("/ep")

    assert order == ["pre1", "pre2", "post2", "post1"]


def test_lightapi_caching(monkeypatch):
    dummy = DummyRedis()
    monkeypatch.setattr(redis, "Redis", lambda *a, **kw: dummy)

    class Endpoint(RestEndpoint):
        class Configuration:
            http_method_names = ["GET"]
            caching_class = RedisCache
            caching_method_names = ["GET"]

        def get(self, request):
            return {"val": "ok"}, 200

    app = LightApi()
    app.register({"/cache": Endpoint})
    star = Starlette(routes=app.routes)
    with TestClient(star) as client:
        r1 = client.get("/cache")
        r2 = client.get("/cache")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert dummy.setex_count == 1


def test_response_decode():
    data = {"foo": "bar"}
    resp = Response(data)
    assert resp.decode() == json.dumps(data)
