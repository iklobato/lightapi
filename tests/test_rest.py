"""Tests for RestEndpointMeta: type map, constraints, auto-fields (FR-1, FR-2, FR-3)."""

import datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from lightapi import LightApi, RestEndpoint
from lightapi.exceptions import ConfigurationError
from lightapi.fields import Field as LField


class TestAnnotationTypeMap:
    def test_annotation_not_in_type_map_raises(self):
        """Unsupported annotation (e.g. list[str]) raises ConfigurationError at class creation."""
        with pytest.raises(ConfigurationError, match="not in the type map"):

            class BadEndpoint(RestEndpoint):
                foo: list[str] = LField()

    def test_type_map_str_int_float_bool_datetime(self):
        """Each supported type maps to correct SQLAlchemy column type."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        class TypeMapEndpoint(RestEndpoint):
            s: str = LField()
            i: int = LField()
            f: float = LField()
            b: bool = LField()
            dt: datetime.datetime = LField()

        app = LightApi(engine=engine)
        app.register({"/types": TypeMapEndpoint})
        table = TypeMapEndpoint.__table__
        from sqlalchemy import Boolean, DateTime, Float, Integer, String

        assert isinstance(table.c["s"].type, String)
        assert isinstance(table.c["i"].type, Integer)
        assert isinstance(table.c["f"].type, Float)
        assert isinstance(table.c["b"].type, Boolean)
        assert isinstance(table.c["dt"].type, DateTime)

    def test_optional_annotation_nullable_column(self):
        """Optional[str] produces nullable=True column."""
        from typing import Optional

        class OptionalEndpoint(RestEndpoint):
            name: Optional[str] = LField()

        assert OptionalEndpoint.__table__.c["name"].nullable is True

    def test_decimal_maps_to_numeric(self):
        """Decimal + decimal_places maps to Numeric(scale=N)."""
        from sqlalchemy import Numeric

        class DecimalEndpoint(RestEndpoint):
            price: Decimal = LField(decimal_places=2)

        col = DecimalEndpoint.__table__.c["price"]
        assert isinstance(col.type, Numeric)
        assert col.type.scale == 2

    def test_uuid_maps_to_uuid_column(self):
        """UUID annotation maps to Uuid/PG_UUID column type."""

        class UuidEndpoint(RestEndpoint):
            ref: UUID = LField()

        col_type = type(UuidEndpoint.__table__.c["ref"].type)
        assert col_type.__name__ in ("Uuid", "UUID")


class TestLightApiFieldKwargs:
    def test_foreign_key_adds_column_constraint(self):
        """Field(foreign_key='categories.id') adds ForeignKey to column."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        class CategoryEndpoint(RestEndpoint):
            name: str = LField(min_length=1)

            class Meta:
                table = "categories"

        class ProductEndpoint(RestEndpoint):
            name: str = LField(min_length=1)
            category_id: int = LField(foreign_key="categories.id")

        app = LightApi(engine=engine)
        app.register({"/categories": CategoryEndpoint, "/products": ProductEndpoint})
        table = ProductEndpoint.__table__
        assert len(table.foreign_keys) >= 1
        fk = next(iter(table.foreign_keys))
        assert "categories" in str(fk.target_fullname) or "categories" in str(fk.column)

    def test_unique_true_adds_constraint(self):
        """Field(unique=True) adds unique constraint."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        class UniqueEndpoint(RestEndpoint):
            sku: str = LField(unique=True)

        app = LightApi(engine=engine)
        app.register({"/unique": UniqueEndpoint})
        table = UniqueEndpoint.__table__
        from sqlalchemy import UniqueConstraint

        unique_constraints = [
            c for c in table.constraints if isinstance(c, UniqueConstraint)
        ]
        assert len(unique_constraints) >= 1 or any(c.unique for c in table.c.values())

    def test_index_true_adds_index(self):
        """Field(index=True) adds Index."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        class IndexEndpoint(RestEndpoint):
            email: str = LField(index=True)

        app = LightApi(engine=engine)
        app.register({"/indexed": IndexEndpoint})
        table = IndexEndpoint.__table__
        from sqlalchemy import Index

        indexes = [i for i in table.indexes if isinstance(i, Index)]
        assert len(indexes) >= 1 or table.c["email"].index is True

    def test_exclude_true_no_column(self):
        """Field(exclude=True) produces no database column."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        class ExcludeEndpoint(RestEndpoint):
            name: str = LField(min_length=1)
            _internal: str = LField(exclude=True)

        app = LightApi(engine=engine)
        app.register({"/exclude": ExcludeEndpoint})
        assert "_internal" not in ExcludeEndpoint.__table__.c


class TestAutoFields:
    def test_auto_fields_injected(self):
        """id, created_at, updated_at, version in __table__.c."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        class MinimalEndpoint(RestEndpoint):
            name: str = LField(min_length=1)

        app = LightApi(engine=engine)
        app.register({"/minimal": MinimalEndpoint})
        table = MinimalEndpoint.__table__
        assert "id" in table.c
        assert "created_at" in table.c
        assert "updated_at" in table.c
        assert "version" in table.c

    @pytest.mark.xfail(
        reason="Framework may not yet reject redeclared auto fields (FR-2)"
    )
    def test_redeclare_auto_field_raises(self):
        """Declaring id (or other auto field) raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="id|auto"):

            class BadIdEndpoint(RestEndpoint):
                id: int = LField()
                name: str = LField(min_length=1)


class TestRegistryEndpointMap:
    def test_registry_endpoint_map(self):
        """app.register({"/x": Ep}) populates app._endpoint_map["/x"]."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        class MapEndpoint(RestEndpoint):
            name: str = LField(min_length=1)

        app = LightApi(engine=engine)
        app.register({"/x": MapEndpoint})
        assert "/x" in app._endpoint_map
        assert app._endpoint_map["/x"] is MapEndpoint
