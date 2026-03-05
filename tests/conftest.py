import pytest
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.engine import Engine

# Legacy v1 test files that are not compatible with v2 API
collect_ignore = [
    "test_rest.py",
    "test_validators.py",
    "test_core.py",
    "test_helpers.py",
    "test_integration.py",
    "test_caching_example.py",
    "test_custom_snippet.py",
    "test_filtering_pagination_example.py",
    "test_from_config.py",
    "test_swagger.py",
    "test_base_endpoint.py",
    "test_additional_features.py",
    "test_cache.py",
    "test_filters.py",
    "test_pagination.py",
]


@pytest.fixture
def engine() -> Engine:
    return sa_create_engine("sqlite:///:memory:")


@pytest.fixture
def app(engine: Engine):
    from lightapi import LightApi
    return LightApi(engine=engine)
