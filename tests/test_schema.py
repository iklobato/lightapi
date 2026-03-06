"""Tests for SchemaFactory and the two generated Pydantic models."""

from typing import get_args, get_origin

import pytest
from pydantic import ValidationError
from sqlalchemy import Column, Integer, LargeBinary, MetaData, Numeric, String, Table

from lightapi.fields import Field as LField
from lightapi.rest import RestEndpoint
from lightapi.schema import SchemaFactory


def _make_endpoint(name: str, annotations: dict, defaults: dict | None = None):
    """Dynamically create a minimal RestEndpoint subclass for testing."""

    ns: dict = {"__annotations__": annotations}
    if defaults:
        ns.update(defaults)
    # Bypass metaclass processing — build schemas directly
    cls = type(name, (object,), ns)
    cls.__annotations__ = annotations
    return cls


class TestSchemaFactoryExcludesAutoFields:
    def test_create_schema_excludes_id(self):
        class SimpleEndpoint(RestEndpoint):
            name: str = LField(min_length=1)

        assert "id" not in SimpleEndpoint.__schema_create__.model_fields
        assert "created_at" not in SimpleEndpoint.__schema_create__.model_fields
        assert "updated_at" not in SimpleEndpoint.__schema_create__.model_fields
        assert "version" not in SimpleEndpoint.__schema_create__.model_fields

    def test_create_schema_includes_user_fields(self):
        class Ep(RestEndpoint):
            title: str = LField(min_length=1)
            count: int = LField(ge=0)

        assert "title" in Ep.__schema_create__.model_fields
        assert "count" in Ep.__schema_create__.model_fields

    def test_read_schema_includes_auto_fields(self):
        class Ep(RestEndpoint):
            name: str = LField(min_length=1)

        fields = Ep.__schema_read__.model_fields
        assert "id" in fields
        assert "created_at" in fields
        assert "version" in fields

    def test_read_schema_has_extra_allow(self):
        class Ep(RestEndpoint):
            name: str = LField(min_length=1)

        config = Ep.__schema_read__.model_config
        assert config.get("extra") == "allow"

    def test_field_constraints_preserved_min_length(self):
        class Ep(RestEndpoint):
            name: str = LField(min_length=3)

        with pytest.raises(ValidationError):
            Ep.__schema_create__.model_validate({"name": "ab"})

    def test_field_constraints_preserved_ge(self):
        class Ep(RestEndpoint):
            qty: int = LField(ge=0)

        with pytest.raises(ValidationError):
            Ep.__schema_create__.model_validate({"qty": -1})

    def test_exclude_field_absent_from_both_schemas(self):
        class Ep(RestEndpoint):
            name: str = LField(min_length=1)
            _secret: float = LField(exclude=True)

        assert "_secret" not in Ep.__schema_create__.model_fields
        assert "_secret" not in Ep.__schema_read__.model_fields

    def test_join_label_passes_through_read_schema(self):
        class Ep(RestEndpoint):
            name: str = LField(min_length=1)

        result = Ep.__schema_read__.model_validate(
            {
                "name": "x",
                "id": 1,
                "version": 1,
                "created_at": None,
                "updated_at": None,
                "extra_label": "joined",
            }
        )
        assert result.model_dump()["extra_label"] == "joined"


class TestBuildFromReflectedTable:
    """Unit tests for SchemaFactory.build_from_reflected_table()."""

    def test_create_schema_excludes_auto_fields(self):
        meta = MetaData()
        table = Table(
            "test_table",
            meta,
            Column("id", Integer, primary_key=True),
            Column("sku", String),
            Column("name", String),
            Column("version", Integer),
        )

        # Use a minimal cls - build_from_reflected_table only needs cls.__name__
        class FakeEndpoint:
            __name__ = "FakeEndpoint"

        schema_create, _ = SchemaFactory.build_from_reflected_table(FakeEndpoint, table)
        assert "id" not in schema_create.model_fields
        assert "created_at" not in schema_create.model_fields
        assert "updated_at" not in schema_create.model_fields
        assert "version" not in schema_create.model_fields

    def test_create_schema_includes_business_columns(self):
        meta = MetaData()
        table = Table(
            "test_table",
            meta,
            Column("id", Integer, primary_key=True),
            Column("sku", String),
            Column("name", String),
            Column("price", Numeric(10, 2)),
        )

        class FakeEndpoint:
            __name__ = "FakeEndpoint"

        schema_create, _ = SchemaFactory.build_from_reflected_table(FakeEndpoint, table)
        assert "sku" in schema_create.model_fields
        assert "name" in schema_create.model_fields
        assert "price" in schema_create.model_fields

    def test_read_schema_includes_all_columns(self):
        meta = MetaData()
        table = Table(
            "test_table",
            meta,
            Column("id", Integer, primary_key=True),
            Column("sku", String),
            Column("name", String),
        )

        class FakeEndpoint:
            __name__ = "FakeEndpoint"

        _, schema_read = SchemaFactory.build_from_reflected_table(FakeEndpoint, table)
        assert "id" in schema_read.model_fields
        assert "sku" in schema_read.model_fields
        assert "name" in schema_read.model_fields
        assert "created_at" in schema_read.model_fields
        assert "updated_at" in schema_read.model_fields
        assert "version" in schema_read.model_fields

    def test_nullable_columns_become_optional(self):
        meta = MetaData()
        table = Table(
            "test_table",
            meta,
            Column("id", Integer, primary_key=True),
            Column("optional_field", String, nullable=True),
        )

        class FakeEndpoint:
            __name__ = "FakeEndpoint"

        schema_create, schema_read = SchemaFactory.build_from_reflected_table(
            FakeEndpoint, table
        )
        # optional_field is nullable, so it should be Optional[str]
        ann = schema_create.model_fields["optional_field"].annotation
        origin = get_origin(ann)
        args = get_args(ann)
        assert origin is not None  # Union type
        assert type(None) in args

    def test_maps_integer_string_float(self):
        meta = MetaData()
        table = Table(
            "test_table",
            meta,
            Column("id", Integer, primary_key=True),
            Column("sku", String, nullable=False),
            Column("name", String, nullable=False),
            Column("price", Numeric(10, 2), nullable=False),
        )

        class FakeEndpoint:
            __name__ = "FakeEndpoint"

        schema_create, _ = SchemaFactory.build_from_reflected_table(FakeEndpoint, table)
        validated = schema_create.model_validate(
            {"sku": "X", "name": "Y", "price": 1.5}
        )
        assert validated.sku == "X"
        assert validated.name == "Y"
        assert float(validated.price) == 1.5

    def test_unknown_type_uses_any(self):
        meta = MetaData()
        table = Table(
            "test_table",
            meta,
            Column("id", Integer, primary_key=True),
            Column("blob_col", LargeBinary, nullable=True),
        )

        class FakeEndpoint:
            __name__ = "FakeEndpoint"

        schema_create, _ = SchemaFactory.build_from_reflected_table(FakeEndpoint, table)
        # Unknown type falls back to Any; should not raise ValidationError
        validated = schema_create.model_validate({"blob_col": b"bytes"})
        assert validated.blob_col == b"bytes"
