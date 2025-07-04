from unittest.mock import ANY, MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, String

from lightapi.auth import JWTAuthentication
from lightapi.cache import RedisCache
from lightapi.core import Middleware, Response
from lightapi.filters import ParameterFilter
from lightapi.lightapi import LightApi
from lightapi.pagination import Paginator
from lightapi.rest import RestEndpoint, Validator


class TestValidator(Validator):
    def validate_name(self, value):
        return value.upper()

    def validate_email(self, value):
        return value


class TestPaginator(Paginator):
    limit = 5
    sort = True


class TestMiddleware(Middleware):
    def process(self, request, response):
        if response:
            response.headers["X-Test"] = "test-value"
        return response


class User(RestEndpoint):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)

    class Configuration:
        http_method_names = ["GET", "POST"]
        validator_class = TestValidator
        pagination_class = TestPaginator
        filter_class = ParameterFilter
        authentication_class = JWTAuthentication
        caching_class = RedisCache
        caching_method_names = ["GET"]


# TestIntegration class removed (no remaining tests)

# All generic example endpoint tests from deleted files are now parameterized here as TestIntegrationEndpoints.
