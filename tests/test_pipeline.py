"""Tests for the serialization pipeline helpers."""
import pytest

from lightapi.schema import _apply_fields, _row_to_dict, resolve_fields
from lightapi.exceptions import SerializationError


class TestRowToDict:
    def test_dict_passthrough(self):
        d = {"id": 1, "name": "x"}
        assert _row_to_dict(d) is d

    def test_row_mapping(self):
        class FakeRow:
            _mapping = {"id": 1, "name": "test"}

        result = _row_to_dict(FakeRow())
        assert result == {"id": 1, "name": "test"}

    def test_orm_instance(self):
        class FakeOrm:
            def __init__(self):
                self.id = 1
                self.name = "orm"
                self._sa_instance_state = "internal"

        result = _row_to_dict(FakeOrm())
        assert result == {"id": 1, "name": "orm"}
        assert "_sa_instance_state" not in result

    def test_unknown_type_raises(self):
        with pytest.raises(SerializationError):
            _row_to_dict(42)

    def test_unknown_type_message(self):
        with pytest.raises(SerializationError, match="int"):
            _row_to_dict(42)


class TestApplyFields:
    def test_none_passthrough(self):
        d = {"id": 1, "name": "x", "secret": "hidden"}
        assert _apply_fields(d, None) is d

    def test_subset_projection(self):
        d = {"id": 1, "name": "x", "secret": "hidden"}
        result = _apply_fields(d, ["id", "name"])
        assert result == {"id": 1, "name": "x"}
        assert "secret" not in result

    def test_empty_fields_list(self):
        d = {"id": 1, "name": "x"}
        assert _apply_fields(d, []) == {}

    def test_fields_not_in_dict_ignored(self):
        d = {"id": 1}
        result = _apply_fields(d, ["id", "missing"])
        assert result == {"id": 1}


class TestJoinLabelPassthrough:
    def test_join_label_in_read_schema(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField

        class Ep(RestEndpoint):
            name: str = LField(min_length=1)

        row_dict = {"id": 1, "name": "x", "version": 1, "created_at": None, "updated_at": None, "category_name": "Books"}
        validated = Ep.__schema_read__.model_validate(row_dict)
        dumped = validated.model_dump()
        assert dumped["category_name"] == "Books"


class TestResolveFields:
    def test_get_returns_read_fields(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField
        from lightapi.config import Serializer

        class Ep(RestEndpoint):
            name: str = LField(min_length=1)
            class Meta:
                serializer = Serializer(read=["id", "name", "tag"], write=["id", "name"])

        assert resolve_fields(Ep, "GET") == ["id", "name", "tag"]

    def test_post_returns_write_fields(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField
        from lightapi.config import Serializer

        class Ep(RestEndpoint):
            name: str = LField(min_length=1)
            class Meta:
                serializer = Serializer(read=["id", "name", "tag"], write=["id", "name"])

        assert resolve_fields(Ep, "POST") == ["id", "name"]

    def test_no_serializer_returns_none(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField

        class Ep(RestEndpoint):
            name: str = LField(min_length=1)

        assert resolve_fields(Ep, "GET") is None
        assert resolve_fields(Ep, "POST") is None
