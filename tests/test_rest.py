from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, String
from starlette.requests import Request

from lightapi.core import Response
from lightapi.rest import RestEndpoint, Validator


class TestValidator(Validator):
    """
    Test validator implementation for testing validation logic.

    This validator implements name validation to demonstrate
    custom validation logic within the REST framework.
    """

    def validate_name(self, value):
        """
        Validate a name field value.

        Args:
            value: The name value to validate.

        Returns:
            str: The validated and transformed name (uppercase).

        Raises:
            ValueError: If the name is less than 3 characters.
        """
        if len(value) < 3:
            raise ValueError("Name too short")
        return value.upper()


class TestModel(RestEndpoint):
    """
    Test endpoint model for testing the RestEndpoint functionality.

    Defines a simple model with basic fields and configuration
    for use in the REST endpoint tests.
    """

    __tablename__ = "test_models"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)

    class Configuration:
        """Configuration for the test model endpoint."""

        http_method_names = ["GET", "POST", "PUT", "DELETE"]
        validator_class = TestValidator

    def post(self, request):
        """
        Handle POST requests for the test model.

        This is a simplified implementation specifically for testing,
        which validates the data but doesn't create a database record.

        Args:
            request: The HTTP request object.

        Returns:
            tuple: A tuple containing the response data and status code.

        Raises:
            Exception: If validation fails.
        """
        try:
            data = getattr(request, "data", {})

            if hasattr(self, "validator"):
                validated_data = self.validator.validate(data)
                data = validated_data

            return {"result": data}, 201
        except Exception as e:
            return {"error": str(e)}, 400


class TestRestEndpoint:
    """
    Test suite for the RestEndpoint class functionality.

    Tests various aspects of the RestEndpoint implementation,
    including model definition, configuration, setup, and HTTP methods.
    """

    def test_model_definition(self):
        """Test that the model definition is correctly set up."""
        assert TestModel.__tablename__ == "test_models"
        assert hasattr(TestModel, "id")
        assert hasattr(TestModel, "name")
        assert hasattr(TestModel, "email")

    def test_configuration(self):
        """Test that the model configuration is correctly set up."""
        assert TestModel.Configuration.http_method_names == [
            "GET",
            "POST",
            "PUT",
            "DELETE",
        ]
        assert TestModel.Configuration.validator_class == TestValidator

    def test_setup(self):
        """Test that the endpoint setup correctly initializes components."""
        endpoint = TestModel()
        mock_request = MagicMock()
        mock_session = MagicMock()

        endpoint._setup(mock_request, mock_session)

        assert endpoint.request == mock_request
        assert endpoint.session == mock_session
        assert hasattr(endpoint, "validator")

    def test_get_method(self):
        """Test that the GET method returns the expected response."""
        endpoint = TestModel()
        mock_request = MagicMock()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.all.return_value = []

        endpoint._setup(mock_request, mock_session)
        response, status_code = endpoint.get(mock_request)

        assert status_code == 200
        assert "results" in response
        assert isinstance(response["results"], list)

    def test_post_method(self):
        """Test that the POST method correctly validates and returns data."""
        endpoint = TestModel()
        mock_request = MagicMock()
        mock_request.data = {"name": "Test", "email": "test@example.com"}
        mock_session = MagicMock()

        endpoint._setup(mock_request, mock_session)

        response, status_code = endpoint.post(mock_request)

        assert status_code == 201
        assert "result" in response
        assert response["result"]["name"] == "TEST"


class TestValidatorFunctionality:
    """
    Test suite for the Validator class functionality.

    Tests validation methods and error handling to ensure
    validators correctly process input data.
    """

    def test_validation(self):
        """Test that validation methods correctly validate and transform data."""
        validator = TestValidator()

        with pytest.raises(ValueError):
            validator.validate_name("ab")

        result = validator.validate_name("test")
        assert result == "TEST"
