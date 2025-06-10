from unittest.mock import MagicMock

from sqlalchemy import Column, Integer, String

from lightapi.auth import JWTAuthentication
from lightapi.cache import RedisCache
from lightapi.filters import ParameterFilter
from lightapi.pagination import Paginator
from lightapi.rest import RestEndpoint, Validator


def create_mock_request(
    method="GET", data=None, headers=None, query_params=None, path_params=None
):
    mock_request = MagicMock()
    mock_request.method = method
    mock_request.data = data or {}
    mock_request.headers = headers or {}
    mock_request.query_params = query_params or {}
    mock_request.path_params = path_params or {}
    return mock_request


def create_mock_session():
    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_session.query.return_value = mock_query
    mock_filter = MagicMock()
    mock_query.filter_by.return_value = mock_filter
    mock_first = MagicMock()
    mock_filter.first.return_value = mock_first
    mock_all = []
    mock_query.all.return_value = mock_all

    return mock_session


class TestValidator(Validator):
    def validate_name(self, value):
        return value.upper()

    def validate_email(self, value):
        if "@" not in value:
            raise ValueError("Invalid email")
        return value


class TestPaginator(Paginator):
    limit = 5
    sort = True


class TestFilter(ParameterFilter):
    pass


class TestEndpoint(RestEndpoint):
    __tablename__ = "test_models"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)

    class Configuration:
        http_method_names = ["GET", "POST", "PUT", "DELETE"]
        validator_class = TestValidator
        pagination_class = TestPaginator
        filter_class = TestFilter
        authentication_class = JWTAuthentication
        caching_class = RedisCache
        caching_method_names = ["GET"]


def setup_endpoint(endpoint_class=TestEndpoint, session=None, request=None):
    if session is None:
        session = create_mock_session()
    if request is None:
        request = create_mock_request()

    endpoint = endpoint_class()
    endpoint._setup(request, session)
    return endpoint
