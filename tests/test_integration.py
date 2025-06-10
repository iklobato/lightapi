from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, String

from lightapi.auth import JWTAuthentication
from lightapi.cache import RedisCache
from lightapi.core import LightApi, Middleware, Response
from lightapi.filters import ParameterFilter
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


class TestIntegration:
    @patch("sqlalchemy.orm.sessionmaker")
    @patch("sqlalchemy.create_engine")
    @patch("lightapi.models.Base.metadata.create_all")
    def test_complete_setup(
        self, mock_create_all, mock_create_engine, mock_sessionmaker
    ):
        # Setup mocks
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_session_factory = MagicMock()
        mock_sessionmaker.return_value = mock_session_factory

        # Create app and register endpoint
        app = LightApi(
            database_url="sqlite:///:memory:",
            swagger_title="Test API",
            swagger_version="1.0.0",
            swagger_description="Test API Description",
        )
        app.add_middleware([TestMiddleware])
        app.register({"/users": User})

        # Check app configuration
        assert len(app.routes) >= 3  # Endpoint route + swagger routes
        assert app.middleware == [TestMiddleware]
        assert app.enable_swagger is True
        assert app.swagger_generator.title == "Test API"

        # Check that core methods were called
        mock_create_engine.assert_called_once_with("sqlite:///:memory:")
        mock_create_all.assert_called_once_with(mock_engine)

    @patch("sqlalchemy.orm.sessionmaker")
    @patch("sqlalchemy.create_engine")
    @patch("lightapi.models.Base.metadata.create_all")
    @patch("uvicorn.run")
    def test_run_app(
        self, mock_run, mock_create_all, mock_create_engine, mock_sessionmaker
    ):
        # Setup mocks
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_session_factory = MagicMock()
        mock_sessionmaker.return_value = mock_session_factory

        # Create app and register endpoint
        app = LightApi(database_url="sqlite:///:memory:")
        app.register({"/users": User})

        # Run the app
        app.run(host="localhost", port=8000, debug=True, reload=True)

        # Check that uvicorn.run was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[1]
        assert call_args["host"] == "localhost"
        assert call_args["port"] == 8000
        assert call_args["log_level"] == "debug"
        assert call_args["reload"] == True
