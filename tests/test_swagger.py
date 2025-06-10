from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, String

from lightapi.rest import RestEndpoint
from lightapi.swagger import SwaggerGenerator, openapi_json_route, swagger_ui_route


class TestEndpoint(RestEndpoint):
    __tablename__ = "test_models"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)

    class Configuration:
        http_method_names = ["GET", "POST"]

    def get(self, request):
        return {"data": "ok"}, 200

    def post(self, request):
        return {"data": "created"}, 201


class TestSwaggerGenerator:
    def test_init(self):
        generator = SwaggerGenerator(
            title="Test API", version="1.0.0", description="Test description"
        )

        assert generator.title == "Test API"
        assert generator.version == "1.0.0"
        assert generator.description == "Test description"
        assert generator.paths == {}
        assert "schemas" in generator.components
        assert "securitySchemes" in generator.components

    def test_register_endpoint(self):
        generator = SwaggerGenerator()
        generator.register_endpoint("/test", TestEndpoint)

        # Check paths
        assert "/test" in generator.paths
        assert "get" in generator.paths["/test"]
        assert "post" in generator.paths["/test"]

        # Check schemas
        assert "TestEndpoint" in generator.components["schemas"]
        assert generator.components["schemas"]["TestEndpoint"]["type"] == "object"

    def test_generate_openapi_spec(self):
        generator = SwaggerGenerator(
            title="Test API", version="1.0.0", description="Test description"
        )
        generator.register_endpoint("/test", TestEndpoint)

        spec = generator.generate_openapi_spec()

        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["title"] == "Test API"
        assert spec["info"]["version"] == "1.0.0"
        assert spec["info"]["description"] == "Test description"
        assert "/test" in spec["paths"]
        assert "components" in spec

    def test_get_swagger_ui(self):
        generator = SwaggerGenerator()
        response = generator.get_swagger_ui()

        assert response.status_code == 200
        assert response.media_type == "text/html"
        assert "swagger-ui" in response.body.decode()

    def test_get_openapi_json(self):
        generator = SwaggerGenerator()
        generator.register_endpoint("/test", TestEndpoint)

        response = generator.get_openapi_json()

        assert response.status_code == 200
        assert response.media_type == "application/json"


class TestSwaggerRoutes:
    def test_swagger_ui_route(self):
        mock_request = MagicMock()
        mock_generator = MagicMock()
        mock_response = MagicMock()

        mock_generator.get_swagger_ui.return_value = mock_response
        mock_request.app.state.swagger_generator = mock_generator

        response = swagger_ui_route(mock_request)

        mock_generator.get_swagger_ui.assert_called_once()
        assert response == mock_response

    def test_openapi_json_route(self):
        mock_request = MagicMock()
        mock_generator = MagicMock()
        mock_response = MagicMock()

        mock_generator.get_openapi_json.return_value = mock_response
        mock_request.app.state.swagger_generator = mock_generator

        response = openapi_json_route(mock_request)

        mock_generator.get_openapi_json.assert_called_once()
        assert response == mock_response
