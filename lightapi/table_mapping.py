"""Where an endpoint's table comes from: its declared fields or an existing table."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import TYPE_CHECKING, Any, Protocol

from pydantic.fields import FieldInfo
from sqlalchemy import Column, MetaData, Table
from sqlalchemy import inspect as sa_inspect

from lightapi.exceptions import ConfigurationError
from lightapi.schema import SchemaFactory

if TYPE_CHECKING:
    from lightapi.session_manager import SessionManager


class TableSource(Protocol):
    """Builds the endpoint's table and maps the endpoint class onto it."""

    def map(self, endpoint_cls: type, session_manager: SessionManager) -> None: ...


class DeclaredTable:
    """A table generated from the endpoint's annotated fields."""

    def __init__(self, columns: list[Column]) -> None:
        self._columns = columns

    def map(self, endpoint_cls: type, session_manager: SessionManager) -> None:
        if endpoint_cls._model_class is not None:
            return

        _strip_field_infos(endpoint_cls, self._columns)
        table = Table(
            _table_name(endpoint_cls, session_manager),
            session_manager.metadata,
            *[column.copy() for column in self._columns],
            extend_existing=True,
            keep_existing=False,
        )
        session_manager.create_tables_now()
        session_manager.registry.map_imperatively(endpoint_cls, table)
        endpoint_cls._model_class = endpoint_cls


class ReflectedTable:
    """A table that already exists in the database (``Meta.reflect``).

    With ``partial`` the endpoint's own fields are added to the reflected columns.
    """

    def __init__(self, partial_columns: list[Column], partial: bool) -> None:
        self._partial_columns = partial_columns
        self._partial = partial

    def map(self, endpoint_cls: type, session_manager: SessionManager) -> None:
        if endpoint_cls._model_class is not None:
            return

        table = self._reflect(
            _table_name(endpoint_cls, session_manager), session_manager
        )
        if self._partial:
            for column in self._partial_columns:
                if column.name not in table.c:
                    table.append_column(column)
            _strip_field_infos(endpoint_cls, list(table.c))

        session_manager.registry.map_imperatively(endpoint_cls, table)
        endpoint_cls._model_class = endpoint_cls
        # The schemas need the columns, which are only known after reflection.
        mapped_table = sa_inspect(endpoint_cls).persist_selectable
        endpoint_cls.__schema_create__, endpoint_cls.__schema_read__ = (
            SchemaFactory.build_from_reflected_table(endpoint_cls, mapped_table)
        )

    def _reflect(self, table_name: str, session_manager: SessionManager) -> Table:
        if session_manager.is_async:
            return _reflect_async(
                session_manager.engine, session_manager.metadata, table_name
            )
        return _reflect_sync(
            session_manager.engine, session_manager.metadata, table_name
        )


def _table_name(endpoint_cls: type, session_manager: SessionManager) -> str:
    base_name = endpoint_cls._meta.get("table") or f"{endpoint_cls.__name__.lower()}s"
    return session_manager.table_name_for(base_name)


def _strip_field_infos(endpoint_cls: type, columns: list[Column]) -> None:
    for column in columns:
        existing = endpoint_cls.__dict__.get(column.name)
        # Remove FieldInfo objects AND bare Ellipsis sentinels. Both block
        # SQLAlchemy's instrumentation from replacing the class attribute
        # with an InstrumentedAttribute, which silently drops the column
        # from the mapper.
        if isinstance(existing, FieldInfo) or existing is ...:
            delattr(endpoint_cls, column.name)


def _reflect_sync(engine: Any, metadata: MetaData, table_name: str) -> Table:
    if table_name not in sa_inspect(engine).get_table_names():
        raise ConfigurationError(
            f"Table '{table_name}' does not exist in the database."
        )
    return Table(table_name, metadata, autoload_with=engine)


def _reflect_async(engine: Any, metadata: MetaData, table_name: str) -> Table:
    def do_reflect(conn: Any) -> None:
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
