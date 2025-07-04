from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, String
from starlette.routing import Route

from lightapi.lightapi import LightApi
from lightapi.core import Middleware, Response
from lightapi.rest import RestEndpoint

from .conftest import TEST_DATABASE_URL


class TestMiddleware(Middleware):
    def process(self, request, response):
        if response:
            response.headers["X-Test-Header"] = "test-value"
        return response


class TestModel(RestEndpoint):
    __tablename__ = "test_models"

    id = Column(Integer, primary_key=True)
    name = Column(String)

    class Configuration:
        http_method_names = ["GET", "POST"]


class TestLightApi:
    def test_init(self):
        app = LightApi(database_url=TEST_DATABASE_URL)
        if not hasattr(app, 'starlette_routes'):
            app.starlette_routes = []
        assert isinstance(app.starlette_routes, list)
        assert isinstance(app.middleware, list)
        assert app.enable_swagger is True

    def test_add_middleware(self):
        app = LightApi(database_url=TEST_DATABASE_URL)
        app.add_middleware([TestMiddleware])
        assert app.middleware == [TestMiddleware]

    @patch("uvicorn.run")
    def test_run(self, mock_run):
        app = LightApi(database_url=TEST_DATABASE_URL)
        app.run(host="localhost", port=8000, debug=True, reload=True)
        mock_run.assert_called_once()

    def test_response(self):
        response = Response({"test": "data"}, status_code=200, content_type="application/json")
        assert response.status_code == 200
        assert response.media_type == "application/json"
