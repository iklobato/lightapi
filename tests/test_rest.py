import pytest
from unittest.mock import MagicMock, patch
from lightapi.rest import RestEndpoint, Validator
from lightapi.core import Response
from sqlalchemy import Column, Integer, String
from starlette.requests import Request


class TestValidator(Validator):
    def validate_name(self, value):
        if len(value) < 3:
            raise ValueError("Name too short")
        return value.upper()


class TestModel(RestEndpoint):
    __tablename__ = 'test_models'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)

    class Configuration:
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
        validator_class = TestValidator


class TestRestEndpoint:
    def test_model_definition(self):
        assert TestModel.__tablename__ == 'test_models'
        assert hasattr(TestModel, 'id')
        assert hasattr(TestModel, 'name')
        assert hasattr(TestModel, 'email')

    def test_configuration(self):
        assert TestModel.Configuration.http_method_names == ['GET', 'POST', 'PUT', 'DELETE']
        assert TestModel.Configuration.validator_class == TestValidator

    def test_setup(self):
        endpoint = TestModel()
        mock_request = MagicMock()
        mock_session = MagicMock()

        endpoint._setup(mock_request, mock_session)

        assert endpoint.request == mock_request
        assert endpoint.session == mock_session
        assert hasattr(endpoint, 'validator')

    def test_get_method(self):
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
        endpoint = TestModel()
        mock_request = MagicMock()
        mock_request.data = {"name": "Test", "email": "test@example.com"}
        mock_session = MagicMock()

        endpoint._setup(mock_request, mock_session)

        with patch.object(endpoint.session, 'add'), patch.object(endpoint.session, 'commit'):
            response, status_code = endpoint.post(mock_request)

            assert status_code == 201
            assert "result" in response


class TestValidator:
    def test_validation(self):
        validator = TestValidator()

        with pytest.raises(ValueError):
            validator.validate_name("ab")

        result = validator.validate_name("test")
        assert result == "TEST"
