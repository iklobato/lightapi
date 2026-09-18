from __future__ import annotations

import datetime
import logging
from decimal import Decimal
from functools import lru_cache
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, create_model
from pydantic.fields import FieldInfo

from lightapi.constants import AUTO_FIELDS
from lightapi.exceptions import ConfigurationError, SerializationError

logger = logging.getLogger(__name__)
_AUTO_FIELDS = AUTO_FIELDS


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


@lru_cache(maxsize=None)
def patch_schema(schema_create: type[BaseModel]) -> type[BaseModel]:
    """``schema_create`` with every field optional, so PATCH can send any subset.

    Cached per create schema: endpoints are a fixed set of classes, and building a
    pydantic model on every PATCH request was measurable work for nothing.
    """
    optional_fields: dict[str, Any] = {
        name: (Optional[field.annotation], None)  # type: ignore[valid-type]
        for name, field in schema_create.model_fields.items()
    }
    return create_model(
        schema_create.__name__.replace("CreateSchema", "PatchSchema"),
        __config__=ConfigDict(from_attributes=True),
        **optional_fields,
    )


# Python types a reflected column is validated as; any other type stays ``Any``.
_REFLECTED_PYTHON_TYPES = frozenset(
    {
        int,
        str,
        float,
        bool,
        Decimal,
        UUID,
        datetime.datetime,
        datetime.date,
        datetime.time,
    }
)


def _reflected_annotation(column: Any) -> Any:
    """Annotation for a reflected column, from SQLAlchemy's own type mapping."""
    try:
        python_type = column.type.python_type
    except NotImplementedError:
        python_type = None
    if python_type in _REFLECTED_PYTHON_TYPES:
        return python_type
    logger.warning(
        "Unknown SQLAlchemy type %s for column %s; using Any",
        type(column.type).__name__,
        column.name,
    )
    return Any


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
        create_fields: dict[str, Any] = {}
        read_fields: dict[str, Any] = {}

        for col in table.c:
            name = col.key
            annotation = _reflected_annotation(col)
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
