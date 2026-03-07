import pytest
import pytest_asyncio
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine


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

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_app(async_engine):
    """LightApi instance backed by an async SQLite engine with a minimal Item endpoint."""
    from pydantic import Field as PydanticField

    from lightapi import LightApi, RestEndpoint
    from lightapi.auth import AllowAny
    from lightapi.config import Authentication

    class _AsyncItem(RestEndpoint):
        name: str = PydanticField(min_length=1)
        active: bool = PydanticField(default=True)

        class Meta:
            authentication = Authentication(permission=AllowAny)

    app = LightApi(engine=async_engine)
    app.register({"/items": _AsyncItem})
    return app
