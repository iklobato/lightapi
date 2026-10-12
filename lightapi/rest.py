"""RestEndpointMeta metaclass and RestEndpoint base class."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import partial
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from starlette.background import BackgroundTasks

    from lightapi.session_manager import SessionManager

from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy import select as sa_select
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.constants import (
    AUTO_FIELDS,
    CRUD_VERBS,
    ApiError,
    HttpVerb,
    TableReflection,
)
from lightapi.exceptions import ConfigurationError
from lightapi.pagination import NoPagination
from lightapi.repository import Repository, RowNotFound, VersionConflict
from lightapi.schema import FieldProjection, SchemaFactory
from lightapi.session import get_async_session, get_sync_session
from lightapi.table_mapping import DeclaredTable, ReflectedTable, TableSource

_AUTO_FIELDS = AUTO_FIELDS

# The client's `version` arrives as a raw JSON value (int, numeric string, or
# whole float); this coerces it the same way pydantic would validate an int
# field, and rejects anything else with a 422 instead of a TypeError deep in
# the repository's `expected_version + 1` arithmetic.
_VERSION_ADAPTER: TypeAdapter[int] = TypeAdapter(int)

_NO_PAGINATION: Final = NoPagination()
_NO_PROJECTION: Final = FieldProjection(None, None, None)


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
            cls._allowed_methods = {verb.value for verb in CRUD_VERBS}
            cls._meta = {}
            return cls

        mcs._process(cls, name, namespace)
        return cls

    @classmethod
    def _process(mcs, cls: type, name: str, namespace: dict[str, Any]) -> None:
        mcs._reject_redeclared_auto_fields(name, namespace)

        meta_obj = namespace.get("Meta") or getattr(cls, "Meta", None)
        reflection = TableReflection.from_meta(getattr(meta_obj, "reflect", None))

        cls._meta = mcs._parsed_meta(name, meta_obj)  # type: ignore[attr-defined]
        cls._allowed_methods = mcs._methods_from_mixins(cls)  # type: ignore[attr-defined]

        if reflection is not None:
            # ReflectedTable.map() builds the schemas once the columns are known.
            cls.__schema_create__ = None  # type: ignore[attr-defined]
            cls.__schema_read__ = None  # type: ignore[attr-defined]
            cls._table_source = ReflectedTable(reflection)  # type: ignore[attr-defined]
            return

        cls.__schema_create__, cls.__schema_read__ = SchemaFactory.build(cls)  # type: ignore[attr-defined]
        cls._table_source = DeclaredTable.from_endpoint(cls, name, namespace)  # type: ignore[attr-defined]

    @staticmethod
    def _reject_redeclared_auto_fields(name: str, namespace: dict[str, Any]) -> None:
        for auto in AUTO_FIELDS:
            if auto in namespace.get("__annotations__", {}):
                raise ConfigurationError(
                    f"RestEndpoint '{name}': '{auto}' is auto-injected "
                    "and must not be redeclared."
                )

    @staticmethod
    def _parsed_meta(name: str, meta_obj: Any) -> dict[str, Any]:
        raw_serializer = getattr(meta_obj, "serializer", None) if meta_obj else None

        # FieldProjection rejects every non-Serializer; a pydantic model gets its
        # own message because it is the mistake people actually make.
        if isinstance(raw_serializer, type) and issubclass(raw_serializer, BaseModel):
            raise ConfigurationError(
                f"Meta.serializer on '{name}' must be a Serializer "
                "instance or subclass, not a BaseModel subclass."
            )

        return {
            "authentication": getattr(meta_obj, "authentication", None),
            "filtering": getattr(meta_obj, "filtering", None),
            "pagination": getattr(meta_obj, "pagination", None),
            "serializer_normalised": FieldProjection.from_serializer(raw_serializer),
            "cache": getattr(meta_obj, "cache", None),
            "table": getattr(meta_obj, "table", None),
        }

    @staticmethod
    def _methods_from_mixins(cls: type) -> set[str]:
        """HTTP methods named by HttpMethod mixins in the MRO; all when none is."""
        allowed = {
            HttpVerb(base._http_method).value
            for base in cls.__mro__[1:]
            if getattr(base, "_http_method", None)
        }
        return allowed or {verb.value for verb in CRUD_VERBS}


_API_ERRORS: Final[dict[type[Exception], ApiError]] = {
    RowNotFound: ApiError.NOT_FOUND,
    VersionConflict: ApiError.VERSION_CONFLICT,
}


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

    def _session_manager_or_raise(self) -> SessionManager:
        """The SessionManager register() bound to this endpoint class."""
        session_manager = getattr(type(self), "_session_manager", None)
        if session_manager is None:
            raise RuntimeError(
                "No session_manager configured. "
                "Ensure LightApi.register() was called with a properly configured app."
            )
        return session_manager

    def _get_engine(self) -> Any:
        """The engine for sync CRUD; an AsyncEngine is unwrapped to its sync one."""
        return self._session_manager_or_raise().sync_engine

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

    def _fields_for(self, verb: HttpVerb) -> list[str] | None:
        """The serializer's field list for a verb, resolved once per request."""
        projection = self._meta.get("serializer_normalised", _NO_PROJECTION)
        return projection.for_method(verb)

    def _serialize_row(self, row: Any, fields: list[str] | None) -> dict[str, Any]:
        d = FieldProjection.apply(SchemaFactory.row_to_dict(row), fields)
        validated = type(self).__schema_read__.model_validate(d)
        result = validated.model_dump(mode="json")
        # Re-apply projection so Optional fields that aren't in the serializer
        # list don't bleed through as null in the response.
        return FieldProjection.apply(result, fields)

    # ── CRUD core: one implementation, always given an open sync Session ─────

    def _list(self, session: Session, request: Request, qs: Any) -> Response:
        pagination = self._meta.get("pagination")
        paginator = pagination.paginator if pagination else _NO_PAGINATION
        qs = self._run_filter_backends(request, qs)
        serialize = partial(self._serialize_row, fields=self._fields_for(HttpVerb.GET))
        return JSONResponse(paginator.render(request, qs, session, serialize))

    def _retrieve(self, session: Session, pk: int) -> Response:
        try:
            row = self._repository(session).get(pk)
        except RowNotFound as exc:
            return _API_ERRORS[type(exc)].response()
        return JSONResponse(self._serialize_row(row, self._fields_for(HttpVerb.GET)))

    def _create(self, session: Session, data: dict[str, Any]) -> Response:
        try:
            validated = type(self).__schema_create__.model_validate(data)
        except ValidationError as exc:
            return ApiError.validation_failed(exc.errors())

        row = self._repository(session).add(validated.model_dump())
        return JSONResponse(
            self._serialize_row(row, self._fields_for(HttpVerb.POST)),
            status_code=HTTPStatus.CREATED,
        )

    def _update(
        self, session: Session, data: dict[str, Any], pk: int, partial: bool
    ) -> Response:
        """PUT/PATCH; the client must send the ``version`` it last read."""
        client_version = data.get("version")
        if client_version is None:
            return ApiError.validation_failed(
                [{"loc": ["version"], "msg": "Field required", "type": "missing"}]
            )
        try:
            client_version = _VERSION_ADAPTER.validate_python(client_version)
        except ValidationError as exc:
            return ApiError.validation_failed(exc.errors())

        repository = self._repository(session)
        try:
            values = self._update_values(data, partial, repository.nullable_columns)
        except ValidationError as exc:
            return ApiError.validation_failed(exc.errors())

        try:
            row = repository.update(pk, client_version, values)
        except (RowNotFound, VersionConflict) as exc:
            return _API_ERRORS[type(exc)].response()
        return JSONResponse(self._serialize_row(row, self._fields_for(HttpVerb.PUT)))

    def _update_values(
        self, data: dict[str, Any], partial: bool, nullable_columns: set[str]
    ) -> dict[str, Any]:
        """Validated column values for an update, without the auto-managed fields."""
        schema_create = type(self).__schema_create__
        if not partial:
            values = schema_create.model_validate(data).model_dump()
            return {k: v for k, v in values.items() if k not in AUTO_FIELDS}

        sent = SchemaFactory.patch_schema(schema_create).model_validate(data)
        # An explicit null clears a nullable column; on any other column it is ignored.
        return {
            k: v
            for k, v in sent.model_dump(exclude_unset=True).items()
            if k not in AUTO_FIELDS and (v is not None or k in nullable_columns)
        }

    def _destroy(self, session: Session, pk: int) -> Response:
        try:
            self._repository(session).delete(pk)
        except RowNotFound as exc:
            return _API_ERRORS[type(exc)].response()
        return Response(status_code=HTTPStatus.NO_CONTENT)

    def _repository(self, session: Session) -> Repository:
        return Repository(type(self)._model_class, session)

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
        """_get_queryset(), awaiting the result of an ``async def queryset``."""
        qs = self._get_queryset(request)
        return await qs if inspect.isawaitable(qs) else qs

    def _get_async_engine(self) -> Any:
        """Return the raw (AsyncEngine) engine for async session creation."""
        return self._session_manager_or_raise().engine

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
