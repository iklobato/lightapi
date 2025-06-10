from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, String
from starlette.routing import Route

from lightapi.core import LightApi, Middleware, Response
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
        assert isinstance(app.routes, list)
        assert isinstance(app.middleware, list)
        assert app.enable_swagger is True

    def test_register_endpoint(self):
        app = LightApi(database_url=TEST_DATABASE_URL)
        app.register({"/test": TestModel})

        # Count routes that are actual endpoints (not docs or other utility routes)
        endpoint_routes = [
            r
            for r in app.routes
            if isinstance(r, Route)
            and not r.path.startswith("/api/docs")
            and r.path != "/openapi.json"
        ]
        assert len(endpoint_routes) == 1

        # Find the route for /test
        test_route = None
        for route in app.routes:
            if isinstance(route, Route) and route.path == "/test":
                test_route = route
                break

        assert test_route is not None
        # Starlette automatically adds HEAD method when GET is included
        assert "GET" in test_route.methods
        assert "POST" in test_route.methods
        # The HEAD method is automatically added by Starlette when GET is included
        assert len(test_route.methods) >= 2

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
        response = Response(
            {"test": "data"}, status_code=200, content_type="application/json"
        )
        assert response.status_code == 200
        assert response.media_type == "application/json"
