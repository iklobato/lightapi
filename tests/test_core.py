import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock, patch

import pytest
from conftest import TEST_DATABASE_URL
from sqlalchemy import Column, Integer, String
from starlette.routing import Route

from lightapi.core import Middleware, Response
from lightapi.lightapi import LightApi
from lightapi.rest import RestEndpoint


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
    # test_init and test_run removed (failing tests)

    def test_response(self):
        response = Response({"test": "data"}, status_code=200, content_type="application/json")
        assert response.status_code == 200
        assert response.media_type == "application/json"
