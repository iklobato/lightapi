from __future__ import annotations

import datetime
import logging
from typing import Any, Optional

from pydantic import ConfigDict, create_model
from pydantic.fields import FieldInfo

from lightapi.exceptions import ConfigurationError, SerializationError

logger = logging.getLogger(__name__)
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
                f"Meta.serializer must be a Serializer subclass, "
                f"got '{serializer.__name__}'."
            )
        instance = serializer()
        return instance.fields, instance.read, instance.write

    if not isinstance(serializer, Serializer):
        raise ConfigurationError(
            f"Meta.serializer must be a Serializer instance or subclass, "
            f"got '{type(serializer).__name__}'."
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
        return {col.key: getattr(row, col.key) for col in row.__mapper__.column_attrs}
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    if hasattr(row, "__dict__"):
        return {k: v for k, v in row.__dict__.items() if not k.startswith("_")}
    raise SerializationError(f"Cannot convert {type(row)} to dict.")


def _apply_fields(d: dict[str, Any], fields: list[str] | None) -> dict[str, Any]:
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
                # create: FieldInfo with constraints for INPUT validation
                create_fields[name] = (annotation, fi)
                # read: Optional[T] so serializer can project out any field
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
        schema_create.model_rebuild()
        schema_read.model_rebuild()
        return schema_create, schema_read

    @staticmethod
    def build_from_reflected_table(cls: type, table: Any) -> tuple[type, type]:
        """Build __schema_create__ and __schema_read__ from reflected table columns.

        Maps SQLAlchemy column types to Pydantic-compatible annotations.
        Excludes id, created_at, updated_at, version from create schema.
        Includes all columns in read schema.
        Uses Optional[T] when column.nullable is True.
        """
        from decimal import Decimal
        from uuid import UUID

        from sqlalchemy import (
            Boolean,
            Date,
            DateTime,
            Float,
            Integer,
            Numeric,
            SmallInteger,
            String,
            Text,
            Time,
        )
        from sqlalchemy.types import BigInteger

        try:
            from sqlalchemy import Uuid as SAUuid
        except ImportError:
            SAUuid = None  # type: ignore[assignment,misc]
        try:
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
        except ImportError:
            PG_UUID = None  # type: ignore[assignment,misc]

        def _col_type_to_annotation(col: Any) -> Any | None:
            """Map SQLAlchemy column type to Pydantic annotation. None if unknown."""
            col_type = type(col.type)
            if isinstance(col.type, (Integer, BigInteger, SmallInteger)):
                return int
            if col_type in (String, Text) or issubclass(col_type, String):
                return str
            if col_type == Numeric or (
                hasattr(Numeric, "__mro__") and Numeric in col_type.__mro__
            ):
                return Decimal
            if col_type == Float or (
                hasattr(Float, "__mro__") and Float in getattr(col_type, "__mro__", ())
            ):
                return float
            if col_type == Boolean:
                return bool
            if col_type == Time or (
                hasattr(Time, "__mro__") and Time in getattr(col_type, "__mro__", ())
            ):
                return datetime.time
            if col_type in (DateTime,) or (
                hasattr(DateTime, "__mro__")
                and DateTime in getattr(col_type, "__mro__", ())
            ):
                return datetime.datetime
            if col_type == Date or (
                hasattr(Date, "__mro__") and Date in getattr(col_type, "__mro__", ())
            ):
                return datetime.date
            if SAUuid is not None and col_type == SAUuid:
                return UUID
            if PG_UUID is not None and col_type == PG_UUID:
                return UUID
            type_name = (
                getattr(col.type, "__visit_name__", "") or col_type.__name__ or ""
            ).lower()
            if type_name in ("integer", "big_integer", "small_integer", "int"):
                return int
            if type_name in (
                "string",
                "varchar",
                "char",
                "text",
                "unicode",
                "unicode_text",
            ):
                return str
            if type_name in ("numeric", "decimal"):
                return Decimal
            if type_name in ("float", "double", "real"):
                return float
            if type_name == "boolean":
                return bool
            if type_name in ("datetime", "timestamp"):
                return datetime.datetime
            if type_name == "date":
                return datetime.date
            if type_name == "time":
                return datetime.time
            if type_name == "uuid":
                return UUID
            logger.warning(
                "Unknown SQLAlchemy type %s for column %s; using Any",
                col_type.__name__,
                col.name,
            )
            return None

        create_fields: dict[str, Any] = {}
        read_fields: dict[str, Any] = {}

        for col in table.c:
            name = col.key
            annotation = _col_type_to_annotation(col)
            if annotation is None:
                annotation = Any
            use_optional = col.nullable
            ann = Optional[annotation] if use_optional else annotation  # type: ignore[valid-type]

            if name not in _AUTO_FIELDS:
                create_fields[name] = (ann, ...)

            read_fields[name] = (Optional[annotation], None)  # type: ignore[valid-type]

        if "id" not in read_fields:
            read_fields["id"] = (Optional[int], None)
        if "created_at" not in read_fields:
            read_fields["created_at"] = (Optional[datetime.datetime], None)
        if "updated_at" not in read_fields:
            read_fields["updated_at"] = (Optional[datetime.datetime], None)
        if "version" not in read_fields:
            read_fields["version"] = (Optional[int], None)

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
        schema_create.model_rebuild()
        schema_read.model_rebuild()
        return schema_create, schema_read


def _strip_lightapi_kwargs(fi: FieldInfo) -> FieldInfo:
    """Copy of FieldInfo with LightAPI-only keys removed from json_schema_extra."""
    from pydantic import Field as pydantic_Field
    from pydantic_core import PydanticUndefined

    from lightapi.fields import _LIGHTAPI_KWARGS

    extra = fi.json_schema_extra or {}
    clean_extra = {k: v for k, v in extra.items() if k not in _LIGHTAPI_KWARGS}

    kwargs: dict[str, Any] = {}
    if fi.default is not PydanticUndefined:
        kwargs["default"] = fi.default
    if fi.default_factory is not None:
        kwargs["default_factory"] = fi.default_factory
    for attr in (
        "title",
        "description",
        "gt",
        "ge",
        "lt",
        "le",
        "min_length",
        "max_length",
        "pattern",
    ):
        val = getattr(fi, attr, None)
        if val is not None:
            kwargs[attr] = val
    if clean_extra:
        kwargs["json_schema_extra"] = clean_extra

    return pydantic_Field(**kwargs)  # type: ignore[return-value]
