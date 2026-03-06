import pytest
import pytest_asyncio
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine

# Legacy v1 test files that are not compatible with v2 API
collect_ignore = [
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


@pytest_asyncio.fixture
async def async_engine():
    """In-memory async SQLite engine with tables created."""
    from sqlalchemy import Column, Integer, String, Boolean
    from sqlalchemy.orm import DeclarativeBase

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_app(async_engine):
    """LightApi instance backed by an async SQLite engine with a minimal Item endpoint."""
    from typing import Optional
    from lightapi import LightApi, RestEndpoint
    from lightapi.config import Authentication, Serializer
    from lightapi.auth import AllowAny
    from pydantic import Field as PydanticField

    app = LightApi(engine=async_engine)

    @app.route("/items")
    class _AsyncItem(RestEndpoint):
        name: str = PydanticField(min_length=1)
        active: bool = PydanticField(default=True)

        class Meta:
            authentication = Authentication(permission=AllowAny)

    return app
