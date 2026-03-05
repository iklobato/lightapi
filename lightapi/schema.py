from __future__ import annotations

from typing import Any

from pydantic import create_model
from pydantic.fields import FieldInfo

from lightapi.exceptions import ConfigurationError, SerializationError

_AUTO_FIELDS = frozenset({"id", "created_at", "updated_at", "version"})


def normalise_serializer(
    serializer: object,
) -> tuple[list[str] | None, list[str] | None, list[str] | None]:
    """Return (fields, read, write) from any Serializer form.

    Accepts a Serializer instance (forms 1-3) or a Serializer subclass (form 4).
    Raises ConfigurationError for non-Serializer types.
    """
    from lightapi.config import Serializer

    if serializer is None:
        return None, None, None

    if isinstance(serializer, type):
        if not issubclass(serializer, Serializer):
            raise ConfigurationError(
                f"Meta.serializer must be a Serializer subclass, got '{serializer.__name__}'."
            )
        instance = serializer()
        return instance.fields, instance.read, instance.write

    if not isinstance(serializer, Serializer):
        raise ConfigurationError(
            f"Meta.serializer must be a Serializer instance or subclass, got '{type(serializer).__name__}'."
        )
    return serializer.fields, serializer.read, serializer.write


def resolve_fields(cls: type, method: str) -> list[str] | None:
    """Return the field list to project for the given HTTP method."""
    fields, read, write = cls._meta.get("serializer_normalised", (None, None, None))
    if fields:
        return fields
    if method.upper() == "GET":
        return read
    return write


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy row or ORM instance to a plain dict.

    Handles four cases:
    - Plain dict → passthrough
    - SQLAlchemy ORM mapped instance (has __mapper__) → use descriptor access
    - SQLAlchemy Row/LegacyRow (has _mapping) → dict(_mapping)
    - Arbitrary object with __dict__ → filter private attrs
    """
    if isinstance(row, dict):
        return row
    # ORM-mapped instance: use descriptor access to trigger lazy loads
    if hasattr(row, "__mapper__"):
        return {
            col.key: getattr(row, col.key)
            for col in row.__mapper__.column_attrs
        }
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    if hasattr(row, "__dict__"):
        return {k: v for k, v in row.__dict__.items() if not k.startswith("_")}
    raise SerializationError(f"Cannot convert {type(row)} to dict.")


def _apply_fields(
    d: dict[str, Any], fields: list[str] | None
) -> dict[str, Any]:
    """Project a dict to only the requested field names.  None → passthrough."""
    if fields is None:
        return d
    return {k: v for k, v in d.items() if k in fields}


class SchemaFactory:
    """Builds Pydantic validation models from a RestEndpoint class."""

    @staticmethod
    def build(cls: type) -> tuple[type, type]:
        """Return (__schema_create__, __schema_read__) for *cls*.

        __schema_create__ — used for POST/PUT/PATCH input validation:
            - excludes id, created_at, updated_at, version
            - from_attributes=True

        __schema_read__ — used for serializing responses:
            - includes all user fields + auto-injected fields (except exclude=True)
            - extra='allow' so join labels pass through without annotation
            - from_attributes=True
        """
        user_annotations: dict[str, Any] = {}
        for base in reversed(cls.__mro__):
            user_annotations.update(
                {
                    k: v
                    for k, v in getattr(base, "__annotations__", {}).items()
                    if not k.startswith("_")
                }
            )

        field_infos: dict[str, FieldInfo] = {}
        for name in user_annotations:
            val = cls.__dict__.get(name) or getattr(cls, name, None)
            if isinstance(val, FieldInfo):
                field_infos[name] = val

        create_fields: dict[str, Any] = {}
        read_fields: dict[str, Any] = {}

        from typing import Optional

        for name, annotation in user_annotations.items():
            if name in _AUTO_FIELDS:
                continue
            fi = field_infos.get(name)
            extra = (fi.json_schema_extra or {}) if fi else {}
            if extra.get("exclude"):
                continue

            if fi is not None:
                # create schema: keep original FieldInfo with all constraints (INPUT validation)
                create_fields[name] = (annotation, fi)
                # read schema: always Optional[T] so the serializer can project out any field
                read_fields[name] = (Optional[annotation], None)  # type: ignore[valid-type]
            else:
                create_fields[name] = (annotation, ...)
                read_fields[name] = (Optional[annotation], None)  # type: ignore[valid-type]

        import datetime
        from typing import Optional

        read_fields["id"] = (Optional[int], None)
        read_fields["created_at"] = (Optional[datetime.datetime], None)
        read_fields["updated_at"] = (Optional[datetime.datetime], None)
        read_fields["version"] = (Optional[int], None)

        from pydantic import ConfigDict

        schema_create = create_model(
            f"{cls.__name__}CreateSchema",
            __config__=ConfigDict(from_attributes=True),
            **create_fields,
        )
        schema_read = create_model(
            f"{cls.__name__}ReadSchema",
            __config__=ConfigDict(from_attributes=True, extra="allow"),
            **read_fields,
        )
        return schema_create, schema_read


def _strip_lightapi_kwargs(fi: FieldInfo) -> FieldInfo:
    """Return a copy of FieldInfo with LightAPI-only keys removed from json_schema_extra."""
    from lightapi.fields import _LIGHTAPI_KWARGS
    from pydantic import Field as pydantic_Field
    from pydantic_core import PydanticUndefined

    extra = fi.json_schema_extra or {}
    clean_extra = {k: v for k, v in extra.items() if k not in _LIGHTAPI_KWARGS}

    kwargs: dict[str, Any] = {}
    if fi.default is not PydanticUndefined:
        kwargs["default"] = fi.default
    if fi.default_factory is not None:
        kwargs["default_factory"] = fi.default_factory
    for attr in ("title", "description", "gt", "ge", "lt", "le", "min_length", "max_length", "pattern"):
        val = getattr(fi, attr, None)
        if val is not None:
            kwargs[attr] = val
    if clean_extra:
        kwargs["json_schema_extra"] = clean_extra

    return pydantic_Field(**kwargs)  # type: ignore[return-value]
