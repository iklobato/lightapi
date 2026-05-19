from typing import Any

from sqlalchemy import Column, MetaData, Table
from sqlalchemy.orm import registry


class TableNameResolver:
    @staticmethod
    def resolve(meta_obj: Any, name: str, session_manager: Any | None = None) -> str:
        base_name = getattr(meta_obj, "table", None) or f"{name.lower()}s"
        if session_manager is not None and getattr(
            session_manager, "_use_test_isolation", False
        ):
            from lightapi.session_manager import get_unique_table_name

            return get_unique_table_name(base_name)
        return base_name


class FieldInfoStripper:
    @staticmethod
    def strip(cls: type, columns: list[Column]) -> None:
        from pydantic.fields import FieldInfo

        for col in columns:
            existing = cls.__dict__.get(col.name)
            if isinstance(existing, FieldInfo):
                try:
                    delattr(cls, col.name)
                except AttributeError:
                    pass


class ImperativeTableBuilder:
    def build(
        self,
        cls: type,
        name: str,
        columns: list[Column],
        meta_obj: Any,
        session_manager: Any | None = None,
    ) -> Table:
        registry_obj, metadata = self._get_registry_and_metadata(session_manager)
        table_name = TableNameResolver.resolve(meta_obj, name, session_manager)

        FieldInfoStripper.strip(cls, columns)

        copied_columns = [col.copy() for col in columns]

        table = Table(
            table_name,
            metadata,
            *copied_columns,
            extend_existing=True,
            keep_existing=False,
        )
        return table

    def _get_registry_and_metadata(
        self, session_manager: Any | None = None
    ) -> tuple[registry, MetaData]:
        from lightapi.session_manager import _GLOBAL_METADATA, _GLOBAL_REGISTRY

        if session_manager is not None:
            return session_manager.registry, session_manager.metadata
        return _GLOBAL_REGISTRY, _GLOBAL_METADATA


class ReflectedTableBuilder:
    def build(
        self,
        cls: type,
        name: str,
        meta_obj: Any,
        partial: bool,
        extra_columns: list[Column] | None = None,
        session_manager: Any | None = None,
    ) -> Table:
        if session_manager is None:
            raise RuntimeError(
                "session_manager is required for reflection. "
                "Ensure LightApi.register() was called with a properly configured app."
            )

        metadata = session_manager.metadata
        engine = session_manager.engine
        table_name = TableNameResolver.resolve(meta_obj, name, session_manager)

        is_async = hasattr(engine, "sync_engine")
        if is_async:
            table = self._reflect_async(engine, metadata, table_name)
        else:
            table = self._reflect_sync(engine, metadata, table_name)

        if partial and extra_columns:
            for col in extra_columns:
                if col.name not in table.c:
                    table.append_column(col)

        if partial:
            FieldInfoStripper.strip(cls, list(table.c))

        return table

    def _reflect_sync(self, engine: Any, metadata: MetaData, table_name: str) -> Table:
        from sqlalchemy import inspect as sa_inspect_engine

        from lightapi.exceptions import ConfigurationError

        inspector = sa_inspect_engine(engine)
        table_names = inspector.get_table_names()
        if table_name not in table_names:
            raise ConfigurationError(
                f"Table '{table_name}' does not exist in the database."
            )
        return Table(table_name, metadata, autoload_with=engine)

    def _reflect_async(self, engine: Any, metadata: MetaData, table_name: str) -> Table:
        import asyncio
        import concurrent.futures

        def do_reflect(conn: Any) -> None:
            metadata.reflect(bind=conn, only=[table_name])

        async def async_reflect() -> None:
            async with engine.connect() as conn:
                await conn.run_sync(do_reflect)

        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, async_reflect()).result()
        except RuntimeError:
            asyncio.run(async_reflect())

        if table_name not in metadata.tables:
            from lightapi.exceptions import ConfigurationError

            raise ConfigurationError(f"Table '{table_name}' could not be reflected.")
        return metadata.tables[table_name]


class TableMapper:
    def __init__(self) -> None:
        self._imperative_builder = ImperativeTableBuilder()
        self._reflected_builder = ReflectedTableBuilder()

    def map_imperatively(
        self,
        cls: type,
        name: str,
        columns: list[Column],
        meta_obj: Any,
        session_manager: Any | None = None,
    ) -> None:
        if getattr(cls, "_model_class", None) is not None:
            return

        table = self._imperative_builder.build(
            cls, name, columns, meta_obj, session_manager
        )
        registry_obj, metadata = self._get_registry_and_metadata(session_manager)

        if session_manager is not None and hasattr(session_manager, "engine"):
            engine = session_manager.engine
            is_async = getattr(session_manager, "_is_async", False)
            if is_async:
                pass
            elif hasattr(engine, "sync_engine"):
                engine = engine.sync_engine
                metadata.create_all(engine)
            else:
                metadata.create_all(engine)

        registry_obj.map_imperatively(cls, table)
        cls._model_class = cls  # type: ignore[attr-defined]

    def map_reflected(
        self,
        cls: type,
        name: str,
        meta_obj: Any,
        partial: bool,
        extra_columns: list[Column] | None = None,
        session_manager: Any | None = None,
    ) -> None:
        table = self._reflected_builder.build(
            cls, name, meta_obj, partial, extra_columns, session_manager
        )
        registry = session_manager.registry

        try:
            from sqlalchemy import inspect as sa_inspect

            sa_inspect(cls)
            cls._model_class = cls  # type: ignore[attr-defined]
            return
        except Exception:
            pass

        registry.map_imperatively(cls, table)
        cls._model_class = cls  # type: ignore[attr-defined]

    def _get_registry_and_metadata(
        self, session_manager: Any | None = None
    ) -> tuple[registry, MetaData]:
        from lightapi.session_manager import _GLOBAL_METADATA, _GLOBAL_REGISTRY

        if session_manager is not None:
            return session_manager.registry, session_manager.metadata
        return _GLOBAL_REGISTRY, _GLOBAL_METADATA


_mapper = TableMapper()


def map_imperatively(
    cls: type,
    name: str,
    columns: list[Column],
    meta_obj: Any,
    session_manager: Any | None = None,
) -> None:
    _mapper.map_imperatively(cls, name, columns, meta_obj, session_manager)


def map_reflected(
    cls: type,
    name: str,
    meta_obj: Any,
    partial: bool,
    extra_columns: list[Column] | None = None,
    session_manager: Any | None = None,
) -> None:
    _mapper.map_reflected(cls, name, meta_obj, partial, extra_columns, session_manager)
