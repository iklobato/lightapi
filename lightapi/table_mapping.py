"""Where an endpoint's table comes from: its declared fields or an existing table."""

from __future__ import annotations

import asyncio
import concurrent.futures
import datetime
import types
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)
from uuid import UUID

from pydantic.fields import FieldInfo
from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Uuid,
)
from sqlalchemy import inspect as sa_inspect

from lightapi.constants import AUTO_FIELDS, TableReflection
from lightapi.exceptions import ConfigurationError
from lightapi.repository import Repository
from lightapi.schema import SchemaFactory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lightapi.rest import RestEndpoint
    from lightapi.session_manager import SessionManager

_TYPE_MAP: Final[dict[Any, Any]] = {
    str: String,
    int: Integer,
    float: Float,
    bool: Boolean,
    datetime.datetime: DateTime,
    Decimal: Numeric,
    UUID: Uuid,
}


class TableSource(ABC):
    """Builds the endpoint's table and maps the endpoint class onto it."""

    @abstractmethod
    def map(
        self, endpoint_cls: type[RestEndpoint], session_manager: SessionManager
    ) -> None: ...

    @staticmethod
    def _table_name(
        endpoint_cls: type[RestEndpoint], session_manager: SessionManager
    ) -> str:
        meta = endpoint_cls._meta  # noqa: SLF001  the endpoint's parsed Meta
        base_name = meta.get("table") or f"{endpoint_cls.__name__.lower()}s"
        return session_manager.table_name_for(base_name)

    @staticmethod
    def _strip_field_infos(
        endpoint_cls: type[RestEndpoint], columns: list[Column[Any]]
    ) -> None:
        for column in columns:
            existing = endpoint_cls.__dict__.get(column.name)
            # Remove FieldInfo objects AND bare Ellipsis sentinels. Both block
            # SQLAlchemy's instrumentation from replacing the class attribute
            # with an InstrumentedAttribute, which silently drops the column
            # from the mapper.
            if isinstance(existing, FieldInfo) or existing is ...:
                delattr(endpoint_cls, column.name)


class DeclaredTable(TableSource):
    """A table generated from the endpoint's annotated fields."""

    def __init__(self, columns: list[Column[Any]]) -> None:
        self._columns = columns

    @classmethod
    def from_endpoint(
        cls, endpoint_cls: type[RestEndpoint], name: str, namespace: dict[str, Any]
    ) -> DeclaredTable:
        """The automatic columns plus one per annotated field (minus exclude=True)."""
        columns: list[Column[Any]] = []
        for field_name, annotation in cls._field_annotations(endpoint_cls).items():
            field_val = namespace.get(field_name) or getattr(
                endpoint_cls, field_name, None
            )
            field_info = field_val if isinstance(field_val, FieldInfo) else None
            column = cls._column_for(name, field_name, annotation, field_info)
            if column is not None:
                columns.append(column)
        return cls(cls._auto_columns() + columns)

    def map(
        self, endpoint_cls: type[RestEndpoint], session_manager: SessionManager
    ) -> None:
        if endpoint_cls._model_class is not None:  # noqa: SLF001  mapped already
            return

        self._strip_field_infos(endpoint_cls, self._columns)
        table = Table(
            self._table_name(endpoint_cls, session_manager),
            session_manager.metadata,
            *self._columns,
            extend_existing=True,
            keep_existing=False,
        )
        session_manager.create_tables_now()
        session_manager.registry.map_imperatively(endpoint_cls, table)
        endpoint_cls._model_class = endpoint_cls  # noqa: SLF001  marks it mapped

    @staticmethod
    def _field_annotations(endpoint_cls: type[RestEndpoint]) -> dict[str, Any]:
        """Public annotated fields of the class and its bases, with real types."""
        # get_type_hints() resolves the string annotations that
        # `from __future__ import annotations` leaves behind.
        try:
            resolved = get_type_hints(endpoint_cls)
        except (NameError, TypeError, SyntaxError, AttributeError):
            # A string annotation that cannot be evaluated; _column_for then
            # reports the raw annotation as not being in the type map.
            resolved = {}

        annotations: dict[str, Any] = {}
        for base in reversed(endpoint_cls.__mro__):
            for field_name, raw in getattr(base, "__annotations__", {}).items():
                if not field_name.startswith("_") and field_name not in AUTO_FIELDS:
                    annotations[field_name] = resolved.get(field_name, raw)
        return annotations

    @staticmethod
    def _column_for(
        endpoint_name: str,
        field_name: str,
        annotation: object,
        field_info: FieldInfo | None,
    ) -> Column[Any] | None:
        """The column for one annotated field; None when the field has exclude=True."""
        raw_extra = field_info.json_schema_extra if field_info is not None else None
        extra: dict[str, Any] = raw_extra if isinstance(raw_extra, dict) else {}
        if extra.get("exclude"):
            return None

        is_opt, inner = DeclaredTable._is_optional(annotation)
        col_type = _TYPE_MAP.get(inner)
        if col_type is None:
            raise ConfigurationError(
                f"RestEndpoint '{endpoint_name}': annotation '{inner}' on field "
                f"'{field_name}' is not in the type map. "
                "Add exclude=True to skip column generation."
            )
        if inner is Decimal:
            col_type = Numeric(scale=extra.get("decimal_places", 10))

        col_args = (
            [ForeignKey(extra["foreign_key"])] if extra.get("foreign_key") else []
        )
        col_kwargs: dict[str, Any] = {"nullable": is_opt}
        if extra.get("unique"):
            col_kwargs["unique"] = True
        if extra.get("index"):
            col_kwargs["index"] = True
        return Column(field_name, col_type, *col_args, **col_kwargs)

    @staticmethod
    def _is_optional(annotation: object) -> tuple[bool, object]:
        """Return (is_optional, inner_type) for an annotation."""
        origin = get_origin(annotation)
        args = get_args(annotation)
        if origin is Union or origin is types.UnionType:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1 and type(None) in args:
                return True, non_none[0]
        return False, annotation

    @staticmethod
    def _auto_columns() -> list[Column[Any]]:
        """id, created_at, updated_at and version, present in every declared table."""
        return [
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("created_at", DateTime, default=Repository.utcnow),
            Column(
                "updated_at",
                DateTime,
                default=Repository.utcnow,
                onupdate=Repository.utcnow,
            ),
            Column("version", Integer, default=1, nullable=False),
        ]


class ReflectedTable(TableSource):
    """A table that already exists in the database (``Meta.reflect``).

    With ``TableReflection.PARTIAL`` the endpoint also declares some of those
    columns as fields.
    """

    def __init__(self, reflection: TableReflection) -> None:
        self._reflection = reflection

    def map(
        self, endpoint_cls: type[RestEndpoint], session_manager: SessionManager
    ) -> None:
        if endpoint_cls._model_class is not None:  # noqa: SLF001  mapped already
            return

        table = self._reflect(
            self._table_name(endpoint_cls, session_manager), session_manager
        )
        if self._reflection is TableReflection.PARTIAL:
            self._strip_field_infos(endpoint_cls, list(table.c))

        session_manager.registry.map_imperatively(endpoint_cls, table)
        endpoint_cls._model_class = endpoint_cls  # noqa: SLF001  marks it mapped
        # The schemas need the columns, which are only known after reflection.
        endpoint_cls.__schema_create__, endpoint_cls.__schema_read__ = (
            SchemaFactory.build_from_reflected_table(endpoint_cls, table)
        )

    def _reflect(self, table_name: str, session_manager: SessionManager) -> Table:
        if session_manager.is_async:
            return self._reflect_async(
                session_manager.engine, session_manager.metadata, table_name
            )
        return self._reflect_sync(
            session_manager.engine, session_manager.metadata, table_name
        )

    @staticmethod
    def _reflect_sync(engine: Engine, metadata: MetaData, table_name: str) -> Table:
        if table_name not in sa_inspect(engine).get_table_names():
            raise ConfigurationError(
                f"Table '{table_name}' does not exist in the database."
            )
        return Table(table_name, metadata, autoload_with=engine)

    @staticmethod
    def _reflect_async(
        engine: AsyncEngine, metadata: MetaData, table_name: str
    ) -> Table:
        def do_reflect(conn: Connection) -> None:
            metadata.reflect(bind=conn, only=[table_name])

        async def async_reflect() -> None:
            async with engine.connect() as conn:
                await conn.run_sync(do_reflect)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(async_reflect())
        else:
            # Already inside a loop (tests, notebooks): reflect on a loop of its own.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, async_reflect()).result()

        if table_name not in metadata.tables:
            raise ConfigurationError(f"Table '{table_name}' could not be reflected.")
        return metadata.tables[table_name]
