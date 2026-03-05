"""Tests for all four Serializer forms and validation guards."""
import pytest

from lightapi.config import Serializer
from lightapi.exceptions import ConfigurationError
from lightapi.schema import normalise_serializer


class TestSerializerForm1:
    def test_no_args_returns_all_none(self):
        s = Serializer()
        f, r, w = normalise_serializer(s)
        assert f is None and r is None and w is None


class TestSerializerForm2:
    def test_fields_subset(self):
        s = Serializer(fields=["id", "name"])
        f, r, w = normalise_serializer(s)
        assert f == ["id", "name"]
        assert r is None and w is None

    def test_fields_and_read_raises(self):
        with pytest.raises(ConfigurationError):
            Serializer(fields=["id"], read=["id"])

    def test_fields_and_write_raises(self):
        with pytest.raises(ConfigurationError):
            Serializer(fields=["id"], write=["id"])


class TestSerializerForm3:
    def test_per_verb(self):
        s = Serializer(read=["id", "name", "tag"], write=["id", "name"])
        f, r, w = normalise_serializer(s)
        assert f is None
        assert r == ["id", "name", "tag"]
        assert w == ["id", "name"]


class TestSerializerForm4:
    def test_subclass_instance_form(self):
        class PubSerializer(Serializer):
            read = ["id", "name", "created_at"]
            write = ["id", "name"]

        f, r, w = normalise_serializer(PubSerializer)
        assert f is None
        assert r == ["id", "name", "created_at"]
        assert w == ["id", "name"]

    def test_subclass_fields_only(self):
        class AuditSer(Serializer):
            fields = ["id", "created_at", "updated_at"]

        f, r, w = normalise_serializer(AuditSer)
        assert f == ["id", "created_at", "updated_at"]

    def test_subclass_defines_fields_and_read_raises_at_class_load(self):
        with pytest.raises(ConfigurationError):
            class BadSerializer(Serializer):
                fields = ["id"]
                read = ["id", "name"]

    def test_empty_subclass_returns_all_none(self):
        class EmptySer(Serializer):
            pass

        f, r, w = normalise_serializer(EmptySer)
        assert f is None and r is None and w is None

    def test_shared_subclass_reused_on_two_endpoints(self):
        from lightapi.rest import RestEndpoint
        from lightapi.fields import Field as LField

        class SharedSer(Serializer):
            read = ["id", "name"]
            write = ["id"]

        class Ep1(RestEndpoint):
            name: str = LField(min_length=1)
            class Meta:
                serializer = SharedSer

        class Ep2(RestEndpoint):
            name: str = LField(min_length=1)
            class Meta:
                serializer = SharedSer

        f1, r1, w1 = Ep1._meta["serializer_normalised"]
        f2, r2, w2 = Ep2._meta["serializer_normalised"]
        assert r1 == r2 == ["id", "name"]
        assert w1 == w2 == ["id"]


class TestSerializerValidationGuards:
    def test_base_model_subclass_raises(self):
        from pydantic import BaseModel

        with pytest.raises(ConfigurationError):
            normalise_serializer(BaseModel)

    def test_non_serializer_class_raises(self):
        with pytest.raises(ConfigurationError):
            normalise_serializer(int)

    def test_none_returns_all_none(self):
        assert normalise_serializer(None) == (None, None, None)
