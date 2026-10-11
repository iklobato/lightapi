from __future__ import annotations

import datetime
import logging
from decimal import Decimal
from functools import lru_cache
from typing import Any, Final, NamedTuple, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, create_model
from pydantic.fields import FieldInfo
from sqlalchemy import Numeric, Uuid

from lightapi.config import Serializer
from lightapi.constants import AUTO_FIELDS, HttpVerb
from lightapi.exceptions import ConfigurationError, SerializationError

logger = logging.getLogger(__name__)


class FieldProjection(NamedTuple):
    """Which fields a response shows: one list for every verb, or read and write lists.

    Lives in ``RestEndpoint._meta["serializer_normalised"]`` as the (fields, read,
    write) tuple it has always been.
    """

    fields: list[str] | None
    read: list[str] | None
    write: list[str] | None

    @classmethod
    def from_serializer(cls, serializer: object) -> FieldProjection:
        """The projection of any Serializer form; no serializer projects nothing.

        Accepts a Serializer instance (forms 1-3) or a Serializer subclass (form 4).
        Raises ConfigurationError for non-Serializer types.
        """
        if serializer is None:
            return cls(None, None, None)

        if isinstance(serializer, type):
            if not issubclass(serializer, Serializer):
                raise ConfigurationError(
                    f"Meta.serializer must be a Serializer subclass, "
                    f"got '{serializer.__name__}'."
                )
            instance = serializer()
            return cls(instance.fields, instance.read, instance.write)

        if not isinstance(serializer, Serializer):
            raise ConfigurationError(
                f"Meta.serializer must be a Serializer instance or subclass, "
                f"got '{type(serializer).__name__}'."
            )
        return cls(serializer.fields, serializer.read, serializer.write)

    def for_method(self, method: str) -> list[str] | None:
        """The field list to project for an HTTP method; None means every field."""
        if self.fields:
            return self.fields
        if method.upper() == HttpVerb.GET:
            return self.read
        return self.write

    @staticmethod
    def apply(d: dict[str, Any], fields: list[str] | None) -> dict[str, Any]:
        """Project a dict to only the requested field names.  None → passthrough."""
        if fields is None:
            return d
        return {k: v for k, v in d.items() if k in fields}


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


# Every read schema carries the auto-managed columns, after the endpoint's own fields.
_AUTO_READ_FIELDS: Final[dict[str, Any]] = {
    "id": (Optional[int], None),
    "created_at": (Optional[datetime.datetime], None),
    "updated_at": (Optional[datetime.datetime], None),
    "version": (Optional[int], None),
}


class SchemaFactory:
    """Builds Pydantic validation models from a RestEndpoint class, and turns rows
    into the dicts those models validate."""

    @staticmethod
    def row_to_dict(row: Any) -> dict[str, Any]:
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
                col.key: getattr(row, col.key) for col in row.__mapper__.column_attrs
            }
        if hasattr(row, "_mapping"):
            return dict(row._mapping)
        if hasattr(row, "__dict__"):
            return {k: v for k, v in row.__dict__.items() if not k.startswith("_")}
        raise SerializationError(f"Cannot convert {type(row)} to dict.")

    @staticmethod
    @lru_cache(maxsize=None)
    def patch_schema(schema_create: type[BaseModel]) -> type[BaseModel]:
        """``schema_create`` with every field optional, so PATCH can send any subset.

        Cached per create schema: endpoints are a fixed set of classes, and building
        a pydantic model on every PATCH request was measurable work for nothing.
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

    @staticmethod
    def _reflected_annotation(column: Any) -> Any:
        """Annotation for a reflected column, from SQLAlchemy's own type mapping."""
        # Two answers of python_type differ from what released versions validated,
        # and clients see the difference (a Decimal is a JSON string, a float a JSON
        # number): Float, Double and REAL are Numeric subclasses and have always
        # been Decimal here, and a Uuid column is a UUID whatever its as_uuid flag.
        if isinstance(column.type, Numeric):
            return Decimal
        if isinstance(column.type, Uuid):
            return UUID
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

    @staticmethod
    def _schema_pair(
        endpoint_name: str, create_fields: dict[str, Any], read_fields: dict[str, Any]
    ) -> tuple[type, type]:
        """(create schema, read schema) for an endpoint.

        create: input validation for POST/PUT/PATCH.
        read: response serialization; ``extra="allow"`` lets join labels through.
        """
        missing_auto = {
            k: v for k, v in _AUTO_READ_FIELDS.items() if k not in read_fields
        }
        schema_create = create_model(
            f"{endpoint_name}CreateSchema",
            __config__=ConfigDict(from_attributes=True),
            **create_fields,
        )
        schema_read = create_model(
            f"{endpoint_name}ReadSchema",
            __config__=ConfigDict(from_attributes=True, extra="allow"),
            **read_fields,
            **missing_auto,
        )
        schema_create.model_rebuild()
        schema_read.model_rebuild()
        return schema_create, schema_read

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

        create_fields: dict[str, Any] = {}
        read_fields: dict[str, Any] = {}
        for name, annotation in user_annotations.items():
            if name in AUTO_FIELDS:
                continue
            value = cls.__dict__.get(name) or getattr(cls, name, None)
            field_info = value if isinstance(value, FieldInfo) else None
            extra = (
                (field_info.json_schema_extra or {}) if field_info is not None else {}
            )
            if extra.get("exclude"):
                continue

            # create keeps the Field() constraints; read is Optional so a
            # serializer can project any field out.
            default = field_info if field_info is not None else ...
            create_fields[name] = (annotation, default)
            read_fields[name] = (Optional[annotation], None)  # type: ignore[valid-type]

        return SchemaFactory._schema_pair(cls.__name__, create_fields, read_fields)

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
            annotation = SchemaFactory._reflected_annotation(col)
            if col.key not in AUTO_FIELDS:
                required = Optional[annotation] if col.nullable else annotation  # type: ignore[valid-type]
                create_fields[col.key] = (required, ...)
            read_fields[col.key] = (Optional[annotation], None)  # type: ignore[valid-type]

        return SchemaFactory._schema_pair(cls.__name__, create_fields, read_fields)
