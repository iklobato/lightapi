import json
from unittest.mock import MagicMock

import pytest
import redis
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from lightapi.cache import RedisCache
from lightapi.core import Middleware, Response
from lightapi.filters import ParameterFilter
from lightapi.lightapi import LightApi
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


def test_response_decode():
    data = {"foo": "bar"}
    resp = Response(data)
    assert resp.decode() == json.dumps(data)
