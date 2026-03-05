"""Tests for US6: reflect=True with AsyncEngine uses run_sync."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import Field as PydanticField
from sqlalchemy import Column, Integer, String, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase

from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication


class _ReflBase(DeclarativeBase):
    pass


class _PreExisting(_ReflBase):
    __tablename__ = "preexisting_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String(200))


@pytest_asyncio.fixture
async def pre_populated_engine():
    """Async engine with a pre-existing table and one row."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_ReflBase.metadata.create_all)
        await conn.execute(
            text("INSERT INTO preexisting_items (label) VALUES ('hello')")
        )
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(_ReflBase.metadata.drop_all)
    await engine.dispose()


async def test_reflect_true_with_async_engine_uses_run_sync(pre_populated_engine):
    """reflect=True endpoint on async engine creates tables without error."""

    class ReflectedItem(RestEndpoint):
        class Meta:
            reflect = True
            table_name = "preexisting_items"
            authentication = Authentication(permission=AllowAny)

    app = LightApi(engine=pre_populated_engine)
    app.register({"/reflected": ReflectedItem})
    starlette_app = app.build_app()

    async with AsyncClient(
        transport=ASGITransport(app=starlette_app), base_url="http://test"
    ) as c:
        r = await c.get("/reflected")
    assert r.status_code == 200


async def test_reflected_columns_available(pre_populated_engine):
    """Reflected endpoint returns rows with expected columns."""

    class ReflectedItem2(RestEndpoint):
        class Meta:
            reflect = True
            table_name = "preexisting_items"
            authentication = Authentication(permission=AllowAny)

    app = LightApi(engine=pre_populated_engine)
    app.register({"/reflected2": ReflectedItem2})
    starlette_app = app.build_app()

    async with AsyncClient(
        transport=ASGITransport(app=starlette_app), base_url="http://test"
    ) as c:
        r = await c.get("/reflected2")
    assert r.status_code == 200
    results = r.json().get("results", [])
    assert len(results) >= 1
    assert "label" in results[0]
