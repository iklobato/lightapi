"""RestEndpointMeta metaclass and RestEndpoint base class."""

from __future__ import annotations

import asyncio
import datetime
from collections.abc import Callable
from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING, Any, get_args, get_origin
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from starlette.background import BackgroundTasks

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
    delete,
    update,
)
from sqlalchemy import select as sa_select
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.constants import (
    AUTO_FIELDS,
    RESPONSE_KEY_DETAIL,
    HTTPStatus,
)
from lightapi.exceptions import ConfigurationError
from lightapi.pagination import NoPagination
from lightapi.schema import (
    SchemaFactory,
    _apply_fields,
    _row_to_dict,
    normalise_serializer,
    resolve_fields,
)
from lightapi.session import get_async_session, get_sync_session
from lightapi.table_mapping import DeclaredTable, ReflectedTable, TableSource

_AUTO_FIELDS = AUTO_FIELDS

_TYPE_MAP: dict[Any, Any] = {
    str: String,
    int: Integer,
    float: Float,
    bool: Boolean,
    datetime.datetime: DateTime,
    Decimal: Numeric,
    UUID: Uuid,
}

_ALL_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})


def _is_optional(annotation: Any) -> tuple[bool, Any]:
    """Return (is_optional, inner_type) for an annotation."""
    import types as _types
    import typing

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is typing.Union or origin is _types.UnionType:  # type: ignore[attr-defined]
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and type(None) in args:
            return True, non_none[0]
    return False, annotation


class RestEndpointMeta(type):
    """Metaclass: annotated RestEndpoint subclasses → mapped SQLAlchemy tables."""

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        if name == "RestEndpoint":
            return cls

        is_base_only = kwargs.get("base_only", False) or namespace.get(
            "_base_only", False
        )
        if is_base_only:
            cls._allowed_methods = set(_ALL_METHODS)
            cls._meta = {}
            return cls

        mcs._process(cls, name, namespace)
        return cls

    @staticmethod
    def _process(cls: type, name: str, namespace: dict[str, Any]) -> None:
        _reject_redeclared_auto_fields(name, namespace)

        meta_obj = namespace.get("Meta") or getattr(cls, "Meta", None)
        reflect = getattr(meta_obj, "reflect", False) if meta_obj else False
        is_reflected = reflect is True or reflect == "full" or reflect == "partial"

        cls._meta = _parsed_meta(name, meta_obj)  # type: ignore[attr-defined]
        cls._allowed_methods = _allowed_methods(cls)  # type: ignore[attr-defined]

        if is_reflected:
            # ReflectedTable.map() builds the schemas once the columns are known.
            cls.__schema_create__ = None  # type: ignore[attr-defined]
            cls.__schema_read__ = None  # type: ignore[attr-defined]
            cls._table_source = ReflectedTable(partial=reflect == "partial")  # type: ignore[attr-defined]
            return

        columns = [] if reflect else _declared_columns(cls, name, namespace)
        cls.__schema_create__, cls.__schema_read__ = SchemaFactory.build(cls)  # type: ignore[attr-defined]
        cls._table_source = DeclaredTable(_auto_columns() + columns)  # type: ignore[attr-defined]


def _reject_redeclared_auto_fields(name: str, namespace: dict[str, Any]) -> None:
    for auto in _AUTO_FIELDS:
        if auto in namespace.get("__annotations__", {}):
            raise ConfigurationError(
                f"RestEndpoint '{name}': '{auto}' is auto-injected "
                "and must not be redeclared."
            )


def _field_annotations(cls: type) -> dict[str, Any]:
    """Public annotated fields of the class and its bases, with real types."""
    import typing

    # get_type_hints() resolves the string annotations that
    # `from __future__ import annotations` leaves behind.
    try:
        resolved = typing.get_type_hints(cls)
    except Exception:
        resolved = {}

    annotations: dict[str, Any] = {}
    for base in reversed(cls.__mro__):
        for field_name, raw in getattr(base, "__annotations__", {}).items():
            if not field_name.startswith("_") and field_name not in _AUTO_FIELDS:
                annotations[field_name] = resolved.get(field_name, raw)
    return annotations


def _declared_columns(cls: type, name: str, namespace: dict[str, Any]) -> list[Column]:
    from pydantic.fields import FieldInfo

    columns: list[Column] = []
    for field_name, annotation in _field_annotations(cls).items():
        field_val = namespace.get(field_name) or getattr(cls, field_name, None)
        field_info = field_val if isinstance(field_val, FieldInfo) else None
        column = _column_for(name, field_name, annotation, field_info)
        if column is not None:
            columns.append(column)
    return columns


def _column_for(
    endpoint_name: str, field_name: str, annotation: Any, field_info: Any
) -> Column | None:
    """The column for one annotated field; None when the field has exclude=True."""
    extra: dict[str, Any] = (field_info.json_schema_extra or {}) if field_info else {}
    if extra.get("exclude"):
        return None

    is_opt, inner = _is_optional(annotation)
    col_type = _TYPE_MAP.get(inner)
    if col_type is None:
        raise ConfigurationError(
            f"RestEndpoint '{endpoint_name}': annotation '{inner}' on field "
            f"'{field_name}' is not in the type map. "
            "Add exclude=True to skip column generation."
        )
    if inner is Decimal:
        col_type = Numeric(scale=extra.get("decimal_places", 10))

    col_args = [ForeignKey(extra["foreign_key"])] if extra.get("foreign_key") else []
    col_kwargs: dict[str, Any] = {"nullable": is_opt}
    if extra.get("unique"):
        col_kwargs["unique"] = True
    if extra.get("index"):
        col_kwargs["index"] = True
    return Column(field_name, col_type, *col_args, **col_kwargs)


def _auto_columns() -> list[Column]:
    """id, created_at, updated_at and version, injected into every declared table."""
    return [
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("created_at", DateTime, default=datetime.datetime.utcnow),
        Column(
            "updated_at",
            DateTime,
            default=datetime.datetime.utcnow,
            onupdate=datetime.datetime.utcnow,
        ),
        Column("version", Integer, default=1, nullable=False),
    ]


def _parsed_meta(name: str, meta_obj: Any) -> dict[str, Any]:
    raw_serializer = getattr(meta_obj, "serializer", None) if meta_obj else None

    # normalise_serializer() rejects every non-Serializer; a pydantic model gets
    # its own message because it is the mistake people actually make.
    if isinstance(raw_serializer, type):
        from pydantic import BaseModel as PydanticBaseModel

        if issubclass(raw_serializer, PydanticBaseModel):
            raise ConfigurationError(
                f"Meta.serializer on '{name}' must be a Serializer "
                "instance or subclass, not a BaseModel subclass."
            )

    return {
        "authentication": getattr(meta_obj, "authentication", None),
        "filtering": getattr(meta_obj, "filtering", None),
        "pagination": getattr(meta_obj, "pagination", None),
        "serializer_normalised": normalise_serializer(raw_serializer),
        "cache": getattr(meta_obj, "cache", None),
        "reflect": getattr(meta_obj, "reflect", False),
        "table": getattr(meta_obj, "table", None),
    }


def _allowed_methods(cls: type) -> set[str]:
    """HTTP methods named by HttpMethod mixins in the MRO; all of them when none is."""
    allowed = {
        base._http_method
        for base in cls.__mro__[1:]
        if getattr(base, "_http_method", None)
    }
    return allowed or set(_ALL_METHODS)


class RestEndpoint(metaclass=RestEndpointMeta):
    """Base class for all LightAPI endpoints.

    Subclasses declare fields as annotated class attributes using Field().
    The metaclass auto-generates SQLAlchemy columns and Pydantic schemas.
    """

    _model_class: type | None = None
    _table_source: TableSource
    _meta: dict[str, Any]
    _allowed_methods: set[str]

    def __init__(self, **kwargs: Any) -> None:
        self._background: BackgroundTasks | None = None
        self._current_request: Request | None = None
        for k, v in kwargs.items():
            setattr(self, k, v)

    # ── Background task support ───────────────────────────────────────────────

    def background(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Schedule fn as a fire-and-forget background task for the current request."""
        if self._background is None:
            raise RuntimeError("background() called outside request handler")
        self._background.add_task(fn, *args, **kwargs)

    # ── CRUD helpers ──────────────────────────────────────────────────────────

    def _get_engine(self) -> Any:
        cls = type(self)
        session_manager = getattr(cls, "_session_manager", None)

        if session_manager is None:
            raise RuntimeError(
                "No session_manager configured. "
                "Ensure LightApi.register() was called with a properly configured app."
            )

        engine = session_manager.engine

        # Sync callers use the sync engine; if an AsyncEngine was registered, unwrap it.
        try:
            from sqlalchemy.ext.asyncio import AsyncEngine as _AE

            if isinstance(engine, _AE):
                return engine.sync_engine
        except ImportError:
            pass
        return engine

    def _get_queryset(self, request: Request) -> Any:
        cls = type(self)
        qs_attr = cls.__dict__.get("queryset")
        if qs_attr is None:
            qs_attr = getattr(cls, "queryset", None)
        if qs_attr is None:
            return sa_select(cls._model_class)
        if callable(qs_attr):
            return qs_attr(self, request)
        return qs_attr

    def _run_filter_backends(self, request: Request, qs: Any) -> Any:
        filtering = self._meta.get("filtering")
        if not filtering or not filtering.backends:
            return qs
        for backend_cls in filtering.backends:
            qs = backend_cls().filter_queryset(request, qs, self)
        return qs

    def _serialize_row(self, row: Any, method: str) -> dict[str, Any]:
        cls = type(self)
        d = _row_to_dict(row)
        fields = resolve_fields(cls, method)
        d = _apply_fields(d, fields)
        schema = cls.__schema_read__
        validated = schema.model_validate(d)
        result = validated.model_dump(mode="json")
        # Re-apply projection so Optional fields that aren't in the serializer
        # list don't bleed through as null in the response.
        if fields is not None:
            result = {k: v for k, v in result.items() if k in fields}
        return result

    # ── CRUD core: one implementation, always given an open sync Session ─────

    def _list(self, session: Session, request: Request, qs: Any) -> Response:
        pagination = self._meta.get("pagination")
        paginator = pagination.build_paginator() if pagination else NoPagination()
        qs = self._run_filter_backends(request, qs)
        serialize = partial(self._serialize_row, method="GET")
        return JSONResponse(paginator.render(request, qs, session, serialize))

    def _retrieve(self, session: Session, pk: int) -> Response:
        cls = type(self)
        instance = (
            session.execute(
                sa_select(cls._model_class).where(cls._model_class.id == pk)
            )
            .scalars()
            .first()
        )
        if instance is None:
            return JSONResponse(
                {RESPONSE_KEY_DETAIL: "not found"}, status_code=HTTPStatus.NOT_FOUND
            )
        return JSONResponse(self._serialize_row(instance, "GET"))

    def _create(self, session: Session, data: dict[str, Any]) -> Response:
        from pydantic import ValidationError

        cls = type(self)
        try:
            validated = cls.__schema_create__.model_validate(data)
        except ValidationError as exc:
            return JSONResponse(
                {RESPONSE_KEY_DETAIL: exc.errors()},
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )

        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        instance = cls._model_class(
            **validated.model_dump(),
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(instance)
        session.flush()  # executes INSERT, populates auto-increment id
        session.refresh(instance)  # re-loads DB-generated columns
        return JSONResponse(
            self._serialize_row(instance, "POST"), status_code=HTTPStatus.CREATED
        )

    def _update(
        self, session: Session, data: dict[str, Any], pk: int, partial: bool
    ) -> Response:
        """PUT/PATCH with optimistic locking on the ``version`` column."""
        from pydantic import ValidationError

        client_version = data.get("version")
        if client_version is None:
            return JSONResponse(
                {
                    RESPONSE_KEY_DETAIL: [
                        {"loc": ["version"], "msg": "Field required", "type": "missing"}
                    ]
                },
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )

        cls = type(self)

        try:
            if partial:
                # Build a one-shot model where every field is Optional so that
                # PATCH can supply any subset of fields without validation errors.
                from typing import Optional as _Opt

                from pydantic import ConfigDict as _CD
                from pydantic import create_model as _cm

                patch_fields: dict[str, Any] = {}
                for fname, finfo in cls.__schema_create__.model_fields.items():
                    ann = finfo.annotation
                    patch_fields[fname] = (_Opt[ann], None)  # type: ignore[valid-type]
                PatchSchema = _cm(
                    f"{cls.__name__}PatchSchema",
                    __config__=_CD(from_attributes=True),
                    **patch_fields,
                )
                validated = PatchSchema.model_validate(data)
                # Determine which columns are nullable so explicit null values
                # can clear Optional fields (non-nullable fields still skip None).
                from sqlalchemy import inspect as _sa_inspect

                nullable_cols: set[str] = {
                    attr.key
                    for attr in _sa_inspect(cls._model_class).mapper.column_attrs
                    if any(c.nullable for c in attr.columns)
                }
                update_data = {
                    k: v
                    for k, v in validated.model_dump(exclude_unset=True).items()
                    if k not in _AUTO_FIELDS and (v is not None or k in nullable_cols)
                }
            else:
                validated = cls.__schema_create__.model_validate(data)
                update_data = {
                    k: v
                    for k, v in validated.model_dump().items()
                    if k not in _AUTO_FIELDS
                }
        except ValidationError as exc:
            return JSONResponse(
                {RESPONSE_KEY_DETAIL: exc.errors()},
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )

        update_data.pop("version", None)

        result = session.execute(
            update(cls._model_class)
            .where(
                cls._model_class.id == pk,
                cls._model_class.version == client_version,
            )
            .values(
                **update_data,
                version=client_version + 1,
                updated_at=datetime.datetime.now(datetime.timezone.utc).replace(
                    tzinfo=None
                ),
            )
        )
        if result.rowcount == 0:
            exists = session.execute(
                sa_select(cls._model_class.id).where(cls._model_class.id == pk)
            ).first()
            session.rollback()
            if not exists:
                return JSONResponse(
                    {RESPONSE_KEY_DETAIL: "not found"},
                    status_code=HTTPStatus.NOT_FOUND,
                )
            return JSONResponse(
                {RESPONSE_KEY_DETAIL: "version conflict"},
                status_code=HTTPStatus.CONFLICT,
            )
        # Re-fetch so all columns (including updated_at/version) are current
        instance = (
            session.execute(
                sa_select(cls._model_class).where(cls._model_class.id == pk)
            )
            .scalars()
            .first()
        )
        return JSONResponse(self._serialize_row(instance, "PUT"))

    def _destroy(self, session: Session, pk: int) -> Response:
        cls = type(self)
        stmt = (
            delete(cls._model_class)
            .where(cls._model_class.id == pk)
            .returning(cls._model_class.id)
        )
        if session.execute(stmt).first() is None:
            return JSONResponse(
                {RESPONSE_KEY_DETAIL: "not found"}, status_code=HTTPStatus.NOT_FOUND
            )
        return Response(status_code=HTTPStatus.NO_CONTENT)

    # ── Sync CRUD: the core inside a sync Session ─────────────────────────────

    def list(self, request: Request) -> Response:
        """Handle GET /{path} — return collection."""
        with get_sync_session(self._get_engine()) as session:
            return self._list(session, request, self._get_queryset(request))

    def retrieve(self, request: Request, pk: int) -> Response:
        """Handle GET /{path}/{id}."""
        with get_sync_session(self._get_engine()) as session:
            return self._retrieve(session, pk)

    def create(self, data: dict[str, Any]) -> Response:
        """Handle POST /{path} — validate input and insert row."""
        with get_sync_session(self._get_engine()) as session:
            return self._create(session, data)

    def update(self, data: dict[str, Any], pk: int, partial: bool = False) -> Response:
        """Handle PUT/PATCH /{path}/{id} with optimistic locking."""
        with get_sync_session(self._get_engine()) as session:
            return self._update(session, data, pk, partial)

    def destroy(self, request: Request, pk: int) -> Response:
        """Handle DELETE /{path}/{id}."""
        with get_sync_session(self._get_engine()) as session:
            return self._destroy(session, pk)

    # ── Async CRUD: the same core, run through AsyncSession.run_sync ──────────

    async def _get_queryset_async(self, request: Request) -> Any:
        """Resolve queryset; await if it is a coroutine function."""
        cls = type(self)
        qs_attr = cls.__dict__.get("queryset")
        if qs_attr is None:
            qs_attr = getattr(cls, "queryset", None)
        if qs_attr is None:
            return sa_select(cls._model_class)
        if asyncio.iscoroutinefunction(qs_attr):
            result = await qs_attr(self, request)
            return result
        if callable(qs_attr):
            return qs_attr(self, request)
        return qs_attr

    def _get_async_engine(self) -> Any:
        """Return the raw (AsyncEngine) engine for async session creation."""
        cls = type(self)
        session_manager = getattr(cls, "_session_manager", None)

        if session_manager is None:
            raise RuntimeError(
                "No session_manager configured. "
                "Ensure LightApi.register() was called with a properly configured app."
            )

        return session_manager.engine

    async def _in_async_session(self, work: Callable[[Session], Response]) -> Response:
        async with get_async_session(self._get_async_engine()) as session:
            return await session.run_sync(work)

    async def _list_async(self, request: Request) -> Response:
        """Async list(); an ``async def queryset`` is awaited first."""
        qs = await self._get_queryset_async(request)
        return await self._in_async_session(lambda s: self._list(s, request, qs))

    async def _retrieve_async(self, request: Request, pk: int) -> Response:
        return await self._in_async_session(lambda s: self._retrieve(s, pk))

    async def _create_async(self, data: dict[str, Any]) -> Response:
        return await self._in_async_session(lambda s: self._create(s, data))

    async def _update_async(
        self, data: dict[str, Any], pk: int, partial: bool = False
    ) -> Response:
        return await self._in_async_session(
            lambda s: self._update(s, data, pk, partial)
        )

    async def _destroy_async(self, request: Request, pk: int) -> Response:
        return await self._in_async_session(lambda s: self._destroy(s, pk))
