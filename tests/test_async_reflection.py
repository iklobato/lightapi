"""Tests for US6: reflect=True with AsyncEngine uses run_sync."""

import datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Column, DateTime, Integer, Numeric, String, text
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


class _AsyncProducts(_ReflBase):
    """Table with full CRUD columns for async reflection tests."""

    __tablename__ = "async_products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )
    version = Column(Integer, default=1, nullable=False)


@pytest_asyncio.fixture
async def async_products_engine():
    """Async engine with async_products table for full CRUD reflection tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_ReflBase.metadata.create_all)
    yield engine
    await engine.dispose()


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


class TestAsyncReflectFullCrud:
    """Full CRUD on reflected async endpoint."""

    async def test_async_reflect_post_creates_row(self, async_products_engine):
        class AsyncProductEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "async_products"
                authentication = Authentication(permission=AllowAny)

        app = LightApi(engine=async_products_engine)
        app.register({"/async_products": AsyncProductEndpoint})
        starlette_app = app.build_app()

        async with AsyncClient(
            transport=ASGITransport(app=starlette_app), base_url="http://test"
        ) as c:
            r = await c.post(
                "/async_products",
                json={"sku": "A1", "name": "Widget", "price": "12.50"},
            )
        assert r.status_code == 201
        data = r.json()
        assert data["sku"] == "A1"
        assert data["name"] == "Widget"
        assert float(data["price"]) == 12.50

    async def test_async_reflect_put_updates_row(self, async_products_engine):
        class AsyncProductEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "async_products"
                authentication = Authentication(permission=AllowAny)

        app = LightApi(engine=async_products_engine)
        app.register({"/async_products": AsyncProductEndpoint})
        starlette_app = app.build_app()

        async with AsyncClient(
            transport=ASGITransport(app=starlette_app), base_url="http://test"
        ) as c:
            post_r = await c.post(
                "/async_products",
                json={"sku": "B2", "name": "Gadget", "price": "9.99"},
            )
        assert post_r.status_code == 201
        product = post_r.json()
        product_id = product["id"]
        version = product["version"]

        async with AsyncClient(
            transport=ASGITransport(app=starlette_app), base_url="http://test"
        ) as c:
            put_r = await c.put(
                f"/async_products/{product_id}",
                json={
                    "sku": "B2-v2",
                    "name": "Gadget Pro",
                    "price": "14.99",
                    "version": version,
                },
            )
        assert put_r.status_code == 200
        updated = put_r.json()
        assert updated["sku"] == "B2-v2"
        assert updated["name"] == "Gadget Pro"
        assert float(updated["price"]) == 14.99

    async def test_async_reflect_delete_returns_204(self, async_products_engine):
        class AsyncProductEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "async_products"
                authentication = Authentication(permission=AllowAny)

        app = LightApi(engine=async_products_engine)
        app.register({"/async_products": AsyncProductEndpoint})
        starlette_app = app.build_app()

        async with AsyncClient(
            transport=ASGITransport(app=starlette_app), base_url="http://test"
        ) as c:
            post_r = await c.post(
                "/async_products",
                json={"sku": "C3", "name": "Doomed", "price": "1.00"},
            )
        assert post_r.status_code == 201
        product_id = post_r.json()["id"]

        async with AsyncClient(
            transport=ASGITransport(app=starlette_app), base_url="http://test"
        ) as c:
            del_r = await c.delete(f"/async_products/{product_id}")
        assert del_r.status_code == 204

        async with AsyncClient(
            transport=ASGITransport(app=starlette_app), base_url="http://test"
        ) as c:
            get_r = await c.get(f"/async_products/{product_id}")
        assert get_r.status_code == 404
