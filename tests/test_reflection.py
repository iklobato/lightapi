"""Tests for US8: Database reflection (Meta.reflect)."""

import datetime

import pytest
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    create_engine,
)
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
from lightapi._registry import set_engine
from lightapi.exceptions import ConfigurationError
from lightapi.fields import Field as LField


def _make_engine_with_products_table():
    """Engine with products: id, sku, name, price, created_at, updated_at, version."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    meta = MetaData()
    Table(
        "products",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("sku", String, nullable=False),
        Column("name", String, nullable=False),
        Column("price", Numeric(10, 2), nullable=False),
        Column(
            "created_at",
            DateTime,
            default=datetime.datetime.utcnow,
        ),
        Column(
            "updated_at",
            DateTime,
            default=datetime.datetime.utcnow,
            onupdate=datetime.datetime.utcnow,
        ),
        Column("version", Integer, default=1, nullable=False),
    )
    meta.create_all(engine)
    return engine


def _make_engine_with_partial_table():
    """Engine with partial_docs: id, title, notes, created_at, updated_at, version.
    Notes pre-created so partial reflection can map it (framework does not ALTER DB).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    meta = MetaData()
    Table(
        "partial_docs",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("title", String, nullable=False),
        Column("notes", String, nullable=True, default=""),
        Column(
            "created_at",
            DateTime,
            default=datetime.datetime.utcnow,
        ),
        Column(
            "updated_at",
            DateTime,
            default=datetime.datetime.utcnow,
            onupdate=datetime.datetime.utcnow,
        ),
        Column("version", Integer, default=1, nullable=False),
    )
    meta.create_all(engine)
    return engine


def _make_engine_with_price_integer_table():
    """Engine with type_conflict table: id, price (Integer).
    Used for partial reflect type conflict test - endpoint will declare price: str.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    meta = MetaData()
    Table(
        "type_conflict",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("price", Integer, nullable=False),
    )
    meta.create_all(engine)
    return engine


def _make_engine_with_table(table_name: str = "legacytable"):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    meta = MetaData()
    Table(
        table_name,
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("title", String, nullable=False),
        Column("author", String, nullable=True),
    )
    meta.create_all(engine)
    return engine


class TestFullReflection:
    def test_reflect_existing_table(self):
        engine = _make_engine_with_table("legacytable")

        class LegacyEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "legacytable"

        set_engine(engine)

        app_instance = LightApi(engine=engine)
        app_instance.register({"/legacy": LegacyEndpoint})
        app = app_instance.build_app()
        client = TestClient(app)

        resp = client.get("/legacy")
        assert resp.status_code == 200
        assert "results" in resp.json()

    def test_reflect_missing_table_raises(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        class NoSuchEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "nonexistent_xyz_table"

        app_instance = LightApi(engine=engine)
        with pytest.raises(ConfigurationError, match="does not exist"):
            app_instance.register({"/nosuch": NoSuchEndpoint})


class TestReflectFullCrud:
    def test_reflect_post_creates_row(self):
        engine = _make_engine_with_products_table()
        set_engine(engine)

        class ProductEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "products"

        app_instance = LightApi(engine=engine)
        app_instance.register({"/products": ProductEndpoint})
        app = app_instance.build_app()
        client = TestClient(app)

        resp = client.post(
            "/products",
            json={"sku": "X1", "name": "Widget", "price": "9.99"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["sku"] == "X1"
        assert data["name"] == "Widget"
        assert float(data["price"]) == 9.99

    def test_reflect_put_updates_business_fields(self):
        engine = _make_engine_with_products_table()
        set_engine(engine)

        class ProductEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "products"

        app_instance = LightApi(engine=engine)
        app_instance.register({"/products": ProductEndpoint})
        app = app_instance.build_app()
        client = TestClient(app)

        post_resp = client.post(
            "/products",
            json={"sku": "A1", "name": "Original", "price": "1.00"},
        )
        assert post_resp.status_code == 201
        product = post_resp.json()

        put_resp = client.put(
            f"/products/{product['id']}",
            json={
                "sku": "A2",
                "name": "Updated",
                "price": "2.50",
                "version": product["version"],
            },
        )
        assert put_resp.status_code == 200
        updated = put_resp.json()
        assert updated["sku"] == "A2"
        assert updated["name"] == "Updated"
        assert float(updated["price"]) == 2.50

    def test_reflect_get_list_and_retrieve(self):
        engine = _make_engine_with_products_table()
        set_engine(engine)

        class ProductEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "products"

        app_instance = LightApi(engine=engine)
        app_instance.register({"/products": ProductEndpoint})
        app = app_instance.build_app()
        client = TestClient(app)

        post_resp = client.post(
            "/products",
            json={"sku": "B1", "name": "Item", "price": "5.00"},
        )
        assert post_resp.status_code == 201
        product_id = post_resp.json()["id"]

        list_resp = client.get("/products")
        assert list_resp.status_code == 200
        results = list_resp.json()["results"]
        assert any(r["id"] == product_id for r in results)

        detail_resp = client.get(f"/products/{product_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["sku"] == "B1"

    def test_reflect_patch_partial_update(self):
        engine = _make_engine_with_products_table()
        set_engine(engine)

        class ProductEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "products"

        app_instance = LightApi(engine=engine)
        app_instance.register({"/products": ProductEndpoint})
        app = app_instance.build_app()
        client = TestClient(app)

        post_resp = client.post(
            "/products",
            json={"sku": "C1", "name": "OldName", "price": "3.00"},
        )
        assert post_resp.status_code == 201
        product = post_resp.json()

        patch_resp = client.patch(
            f"/products/{product['id']}",
            json={"name": "NewName", "version": product["version"]},
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["name"] == "NewName"
        assert updated["sku"] == "C1"

    def test_reflect_delete_returns_204(self):
        engine = _make_engine_with_products_table()
        set_engine(engine)

        class ProductEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "products"

        app_instance = LightApi(engine=engine)
        app_instance.register({"/products": ProductEndpoint})
        app = app_instance.build_app()
        client = TestClient(app)

        post_resp = client.post(
            "/products",
            json={"sku": "D1", "name": "ToDelete", "price": "1.00"},
        )
        assert post_resp.status_code == 201
        product_id = post_resp.json()["id"]

        del_resp = client.delete(f"/products/{product_id}")
        assert del_resp.status_code == 204

        get_resp = client.get(f"/products/{product_id}")
        assert get_resp.status_code == 404

    def test_reflect_put_version_conflict_409(self):
        engine = _make_engine_with_products_table()
        set_engine(engine)

        class ProductEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "products"

        app_instance = LightApi(engine=engine)
        app_instance.register({"/products": ProductEndpoint})
        app = app_instance.build_app()
        client = TestClient(app)

        post_resp = client.post(
            "/products",
            json={"sku": "E1", "name": "Conflict", "price": "1.00"},
        )
        assert post_resp.status_code == 201
        product = post_resp.json()

        put_resp = client.put(
            f"/products/{product['id']}",
            json={
                "sku": "E2",
                "name": "Bad",
                "price": "2.00",
                "version": 9999,
            },
        )
        assert put_resp.status_code == 409

    def test_reflect_put_missing_version_422(self):
        engine = _make_engine_with_products_table()
        set_engine(engine)

        class ProductEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "products"

        app_instance = LightApi(engine=engine)
        app_instance.register({"/products": ProductEndpoint})
        app = app_instance.build_app()
        client = TestClient(app)

        post_resp = client.post(
            "/products",
            json={"sku": "F1", "name": "NoVer", "price": "1.00"},
        )
        assert post_resp.status_code == 201
        product = post_resp.json()

        put_resp = client.put(
            f"/products/{product['id']}",
            json={"sku": "F2", "name": "X", "price": "2.00"},
        )
        assert put_resp.status_code == 422


class TestPartialReflection:
    def test_partial_reflect_appends_new_columns(self):
        engine = _make_engine_with_partial_table()
        set_engine(engine)

        class PartialDocEndpoint(RestEndpoint):
            notes: str = LField(default="")

            class Meta:
                reflect = "partial"
                table = "partial_docs"

        app_instance = LightApi(engine=engine)
        app_instance.register({"/partial_docs": PartialDocEndpoint})
        app = app_instance.build_app()
        client = TestClient(app)

        post_resp = client.post(
            "/partial_docs",
            json={"title": "Doc1", "notes": "my notes"},
        )
        assert post_resp.status_code == 201
        data = post_resp.json()
        assert data["title"] == "Doc1"
        assert data["notes"] == "my notes"

        list_resp = client.get("/partial_docs")
        assert list_resp.status_code == 200
        results = list_resp.json()["results"]
        assert len(results) >= 1
        assert "notes" in results[0]

    def test_partial_reflect_full_crud(self):
        engine = _make_engine_with_partial_table()
        set_engine(engine)

        class PartialDocEndpoint(RestEndpoint):
            notes: str = LField(default="")

            class Meta:
                reflect = "partial"
                table = "partial_docs"

        app_instance = LightApi(engine=engine)
        app_instance.register({"/partial_docs": PartialDocEndpoint})
        app = app_instance.build_app()
        client = TestClient(app)

        post_resp = client.post(
            "/partial_docs",
            json={"title": "CRUD", "notes": "initial"},
        )
        assert post_resp.status_code == 201
        doc = post_resp.json()
        doc_id = doc["id"]

        get_resp = client.get(f"/partial_docs/{doc_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "CRUD"

        put_resp = client.put(
            f"/partial_docs/{doc_id}",
            json={"title": "Updated", "notes": "edited", "version": doc["version"]},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["title"] == "Updated"

        del_resp = client.delete(f"/partial_docs/{doc_id}")
        assert del_resp.status_code == 204

        get_after = client.get(f"/partial_docs/{doc_id}")
        assert get_after.status_code == 404

    @pytest.mark.xfail(
        reason="Framework does not yet validate partial reflect type conflicts (FR-15)"
    )
    def test_partial_reflect_type_conflict_raises(self):
        """Table price=Integer, endpoint price=str → ConfigurationError."""
        engine = _make_engine_with_price_integer_table()
        set_engine(engine)

        class TypeConflictEndpoint(RestEndpoint):
            price: str = LField(min_length=1)

            class Meta:
                reflect = "partial"
                table = "type_conflict"

        app_instance = LightApi(engine=engine)
        with pytest.raises(ConfigurationError, match="conflict|type"):
            app_instance.register({"/type_conflict": TypeConflictEndpoint})
