"""Tests for SchemaFactory and the two generated Pydantic models."""
import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

import pytest
from pydantic import ValidationError

from lightapi.fields import Field
from lightapi.schema import SchemaFactory, _apply_fields, _row_to_dict, resolve_fields
from lightapi.exceptions import SerializationError


def _make_endpoint(name: str, annotations: dict, defaults: dict | None = None):
    """Dynamically create a minimal RestEndpoint subclass for testing."""
    from lightapi.rest import RestEndpoint

    ns: dict = {"__annotations__": annotations}
    if defaults:
        ns.update(defaults)
    # Bypass metaclass processing — build schemas directly
    cls = type(name, (object,), ns)
    cls.__annotations__ = annotations
    return cls


class TestSchemaFactoryExcludesAutoFields:
    def test_create_schema_excludes_id(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField

        class SimpleEndpoint(RestEndpoint):
            name: str = LField(min_length=1)

        assert "id" not in SimpleEndpoint.__schema_create__.model_fields
        assert "created_at" not in SimpleEndpoint.__schema_create__.model_fields
        assert "updated_at" not in SimpleEndpoint.__schema_create__.model_fields
        assert "version" not in SimpleEndpoint.__schema_create__.model_fields

    def test_create_schema_includes_user_fields(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField

        class Ep(RestEndpoint):
            title: str = LField(min_length=1)
            count: int = LField(ge=0)

        assert "title" in Ep.__schema_create__.model_fields
        assert "count" in Ep.__schema_create__.model_fields

    def test_read_schema_includes_auto_fields(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField

        class Ep(RestEndpoint):
            name: str = LField(min_length=1)

        fields = Ep.__schema_read__.model_fields
        assert "id" in fields
        assert "created_at" in fields
        assert "version" in fields

    def test_read_schema_has_extra_allow(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField

        class Ep(RestEndpoint):
            name: str = LField(min_length=1)

        config = Ep.__schema_read__.model_config
        assert config.get("extra") == "allow"

    def test_field_constraints_preserved_min_length(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField

        class Ep(RestEndpoint):
            name: str = LField(min_length=3)

        with pytest.raises(ValidationError):
            Ep.__schema_create__.model_validate({"name": "ab"})

    def test_field_constraints_preserved_ge(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField

        class Ep(RestEndpoint):
            qty: int = LField(ge=0)

        with pytest.raises(ValidationError):
            Ep.__schema_create__.model_validate({"qty": -1})

    def test_exclude_field_absent_from_both_schemas(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField

        class Ep(RestEndpoint):
            name: str = LField(min_length=1)
            _secret: float = LField(exclude=True)

        assert "_secret" not in Ep.__schema_create__.model_fields
        assert "_secret" not in Ep.__schema_read__.model_fields

    def test_join_label_passes_through_read_schema(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField

        class Ep(RestEndpoint):
            name: str = LField(min_length=1)

        result = Ep.__schema_read__.model_validate(
            {"name": "x", "id": 1, "version": 1, "created_at": None, "updated_at": None, "extra_label": "joined"}
        )
        assert result.model_dump()["extra_label"] == "joined"
