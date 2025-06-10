from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, String

from lightapi.core import LightApi
from lightapi.rest import RestEndpoint


class Company(RestEndpoint):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    website = Column(String)

    class Configuration:
        http_method_names = ["GET", "POST"]


class TestExample:
    @patch("sqlalchemy.create_engine")
    @patch("lightapi.models.Base.metadata.create_all")
    @patch("uvicorn.run")
    def test_example_app(self, mock_run, mock_create_all, mock_create_engine):
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        app = LightApi(
            database_url="sqlite:///example.db",
            swagger_title="Example API",
            swagger_version="1.0.0",
            swagger_description="Example API",
        )

        app.register({"/companies": Company})
        app.run(host="0.0.0.0", port=8000, debug=True, reload=True)

        # Check app configuration
        assert len(app.routes) >= 2  # At least one endpoint and swagger routes
        assert app.swagger_generator.title == "Example API"

        # Check that create_engine was called with correct URL
        mock_create_engine.assert_called_once_with("sqlite:///example.db")

        # Check that metadata.create_all was called with the engine
        mock_create_all.assert_called_once_with(mock_engine)

        # Check that uvicorn.run was called with correct parameters
        mock_run.assert_called_once()
        call_args = mock_run.call_args[1]
        assert call_args["host"] == "0.0.0.0"
        assert call_args["port"] == 8000
        assert call_args["log_level"] == "debug"
        assert call_args["reload"] == True
