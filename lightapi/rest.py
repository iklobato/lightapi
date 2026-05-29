"""RestEndpointMeta metaclass and RestEndpoint base class."""

from __future__ import annotations

import asyncio
import datetime
from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING, Any, get_args, get_origin
from uuid import UUID

if TYPE_CHECKING:
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
    delete,
    update,
)
from sqlalchemy import select as sa_select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

try:
    from sqlalchemy import Uuid as SAUuid  # SQLAlchemy 2.0+
except ImportError:
    SAUuid = None  # type: ignore[assignment,misc]

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.constants import (
    AUTO_FIELDS,
    RESPONSE_KEY_DETAIL,
    RESPONSE_KEY_RESULTS,
    HTTPStatus,
)
from lightapi.exceptions import ConfigurationError
from lightapi.schema import (
    SchemaFactory,
    _apply_fields,
    _row_to_dict,
    normalise_serializer,
    resolve_fields,
)

_AUTO_FIELDS = AUTO_FIELDS

_TYPE_MAP: dict[Any, Any] = {
    str: String,
    int: Integer,
    float: Float,
    bool: Boolean,
    datetime.datetime: DateTime,
    Decimal: Numeric,
    UUID: SAUuid if SAUuid is not None else PG_UUID,
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
            cls._fields_info = {}
            return cls

        mcs._process(cls, name, namespace)
        return cls

    @staticmethod
    def _process(cls: type, name: str, namespace: dict[str, Any]) -> None:
        import typing as _typing

        from pydantic.fields import FieldInfo

        # ── Step 1: Collect annotations ──────────────────────────────────────
        # Use get_type_hints() so that PEP-563 string annotations (from
        # `from __future__ import annotations`) are resolved to real types.
        try:
            resolved = _typing.get_type_hints(cls)
        except Exception:
            resolved = {}

        annotations: dict[str, Any] = {}
        for base in reversed(cls.__mro__):
            for k, v in getattr(base, "__annotations__", {}).items():
                if not k.startswith("_") and k not in _AUTO_FIELDS:
                    # Prefer the resolved type; fall back to the raw annotation.
                    annotations[k] = resolved.get(k, v)

        # Remove fields inherited from RestEndpoint itself
        if "RestEndpoint" in [b.__name__ for b in cls.__mro__[1:]]:
            for b in cls.__mro__[1:]:
                if b.__name__ == "RestEndpoint":
                    for k in list(annotations):
                        if k in getattr(b, "__annotations__", {}):
                            annotations.pop(k, None)
                    break

        # Guard: user must not redeclare auto-injected fields
        for auto in _AUTO_FIELDS:
            if auto in namespace.get("__annotations__", {}):
                raise ConfigurationError(
                    f"RestEndpoint '{name}': '{auto}' is auto-injected "
                    "and must not be redeclared."
                )

        # ── Step 2: Build SQLAlchemy columns ─────────────────────────────────
        columns: list[Column] = []
        fields_info: dict[str, FieldInfo] = {}

        meta_class = namespace.get("Meta") or getattr(cls, "Meta", None)
        reflect = getattr(meta_class, "reflect", False) if meta_class else False

        if not reflect:
            for field_name, annotation in annotations.items():
                field_val = namespace.get(field_name) or getattr(cls, field_name, None)
                fi = field_val if isinstance(field_val, FieldInfo) else None
                if fi:
                    fields_info[field_name] = fi

                extra: dict[str, Any] = (fi.json_schema_extra or {}) if fi else {}
                if extra.get("exclude"):
                    continue

                is_opt, inner = _is_optional(annotation)
                col_type = _TYPE_MAP.get(inner)
                if col_type is None:
                    raise ConfigurationError(
                        f"RestEndpoint '{name}': annotation '{inner}' on field "
                        f"'{field_name}' is not in the type map. "
                        "Add exclude=True to skip column generation."
                    )

                col_kwargs: dict[str, Any] = {"nullable": is_opt}
                col_args: list[Any] = []

                if inner is Decimal:
                    scale = extra.get("decimal_places", 10)
                    col_type = Numeric(scale=scale)

                if extra.get("foreign_key"):
                    col_args.append(ForeignKey(extra["foreign_key"]))
                if extra.get("unique"):
                    col_kwargs["unique"] = True
                if extra.get("index"):
                    col_kwargs["index"] = True

                columns.append(Column(field_name, col_type, *col_args, **col_kwargs))

        # ── Step 3: Auto-inject id / created_at / updated_at / version ───────
        auto_cols = [
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

        # ── Step 4: SchemaFactory ─────────────────────────────────────────────
        if reflect is True or reflect == "full" or reflect == "partial":
            cls.__schema_create__ = None  # type: ignore[attr-defined]
            cls.__schema_read__ = None  # type: ignore[attr-defined]
            cls._schema_deferred = True  # type: ignore[attr-defined]
        else:
            cls.__schema_create__, cls.__schema_read__ = SchemaFactory.build(cls)  # type: ignore[attr-defined]
            cls._schema_deferred = False  # type: ignore[attr-defined]

        # ── Step 5: Parse Meta → _meta ────────────────────────────────────────
        meta_obj = namespace.get("Meta") or getattr(cls, "Meta", None)
        raw_serializer = getattr(meta_obj, "serializer", None) if meta_obj else None

        # Guard: Meta.serializer must be Serializer instance/subclass
        if raw_serializer is not None:
            from pydantic import BaseModel as PydanticBaseModel

            if isinstance(raw_serializer, type):
                if issubclass(raw_serializer, PydanticBaseModel):
                    raise ConfigurationError(
                        f"Meta.serializer on '{name}' must be a Serializer "
                        "instance or subclass, not a BaseModel subclass."
                    )
        serialiser_normalised = normalise_serializer(raw_serializer)

        cls._meta = {  # type: ignore[attr-defined]
            "authentication": (
                getattr(meta_obj, "authentication", None) if meta_obj else None
            ),
            "filtering": getattr(meta_obj, "filtering", None) if meta_obj else None,
            "pagination": getattr(meta_obj, "pagination", None) if meta_obj else None,
            "serializer_normalised": serialiser_normalised,
            "cache": getattr(meta_obj, "cache", None) if meta_obj else None,
            "reflect": getattr(meta_obj, "reflect", False) if meta_obj else False,
            "table": getattr(meta_obj, "table", None) if meta_obj else None,
        }
        cls._fields_info = fields_info  # type: ignore[attr-defined]

        # ── Step 6: MRO scan for HttpMethod markers ───────────────────────────

        allowed: set[str] = set()
        for base in cls.__mro__:
            if base is cls:
                continue
            http_method = getattr(base, "_http_method", None)
            if http_method:
                allowed.add(http_method)
        cls._allowed_methods = allowed if allowed else set(_ALL_METHODS)  # type: ignore[attr-defined]

        # ── Step 7: Imperative SQLAlchemy mapping ─────────────────────────────
        if reflect is True or reflect == "full" or reflect == "partial":
            # Defer reflection until LightApi.register() when an engine is available.
            cls._reflect_deferred = True  # type: ignore[attr-defined]
            cls._reflect_partial_columns = columns if reflect == "partial" else []  # type: ignore[attr-defined]
        else:
            cls._reflect_deferred = False  # type: ignore[attr-defined]
            all_columns = auto_cols + columns
            # Store columns for potential re-mapping during registration
            cls._all_columns = all_columns  # type: ignore[attr-defined]

            # Determine table name for test isolation
            table_name = getattr(meta_obj, "table", None) or f"{name.lower()}s"

            # Store table name for potential test isolation during registration
            cls._test_isolation_table_name = table_name  # type: ignore[attr-defined]


class RestEndpoint(metaclass=RestEndpointMeta):
    """Base class for all LightAPI endpoints.

    Subclasses declare fields as annotated class attributes using Field().
    The metaclass auto-generates SQLAlchemy columns and Pydantic schemas.
    """

    _model_class: type
    _meta: dict[str, Any]
    _allowed_methods: set[str]
    _fields_info: dict[str, Any]

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

    def list(self, request: Request) -> Response:
        """Handle GET /{path} — return collection."""
        from sqlalchemy.orm import Session

        engine = self._get_engine()
        pagination_cfg = self._meta.get("pagination")

        with Session(engine) as session:
            qs = self._get_queryset(request)
            qs = self._run_filter_backends(request, qs)

            if pagination_cfg:
                from lightapi.pagination import CursorPaginator, PageNumberPaginator

                if pagination_cfg.style == "cursor":
                    pager = CursorPaginator()
                    rows, next_cursor = pager.paginate(
                        request, qs, session, pagination_cfg.page_size
                    )
                    results = [self._serialize_row(r, "GET") for r in rows]
                    return JSONResponse(pager.wrap(results, next_cursor, None))
                else:
                    pager = PageNumberPaginator()
                    page = int(request.query_params.get("page", 1))
                    rows, total = pager.paginate(
                        request, qs, session, pagination_cfg.page_size
                    )
                    results = [self._serialize_row(r, "GET") for r in rows]
                    return JSONResponse(
                        pager.wrap(
                            request, results, total, page, pagination_cfg.page_size
                        )
                    )

            instances = session.execute(qs).scalars().all()
            results = [self._serialize_row(inst, "GET") for inst in instances]
            return JSONResponse({RESPONSE_KEY_RESULTS: results})

    def retrieve(self, request: Request, pk: int) -> Response:
        """Handle GET /{path}/{id}."""
        from sqlalchemy.orm import Session

        engine = self._get_engine()
        cls = type(self)
        with Session(engine) as session:
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

    def create(self, data: dict[str, Any]) -> Response:
        """Handle POST /{path} — validate input and insert row."""
        from pydantic import ValidationError
        from sqlalchemy.orm import Session

        engine = self._get_engine()
        cls = type(self)
        try:
            validated = cls.__schema_create__.model_validate(data)
        except ValidationError as exc:
            return JSONResponse(
                {RESPONSE_KEY_DETAIL: exc.errors()},
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )

        with Session(engine) as session:
            now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            instance = cls._model_class(
                **validated.model_dump(),
                created_at=now,
                updated_at=now,
                version=1,
            )
            session.add(instance)
            session.flush()  # executes INSERT, populates auto-increment id
            session.refresh(
                instance
            )  # re-loads all columns (including DB-generated ones)
            response_data = self._serialize_row(instance, "POST")
            session.commit()
            return JSONResponse(response_data, status_code=HTTPStatus.CREATED)

    def update(self, data: dict[str, Any], pk: int, partial: bool = False) -> Response:
        """Handle PUT/PATCH /{path}/{id} with optimistic locking."""
        from pydantic import ValidationError
        from sqlalchemy.orm import Session

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

        engine = self._get_engine()
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

        with Session(engine) as session:
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
            response_data = self._serialize_row(instance, "PUT")
            session.commit()
            return JSONResponse(response_data)

    def destroy(self, request: Request, pk: int) -> Response:
        """Handle DELETE /{path}/{id}."""
        from sqlalchemy.orm import Session

        engine = self._get_engine()
        cls = type(self)
        with Session(engine) as session:
            stmt = (
                delete(cls._model_class)
                .where(cls._model_class.id == pk)
                .returning(cls._model_class.id)
            )
            result = session.execute(stmt).first()
            if result is None:
                return JSONResponse(
                    {RESPONSE_KEY_DETAIL: "not found"}, status_code=HTTPStatus.NOT_FOUND
                )
            session.commit()
            return Response(status_code=HTTPStatus.NO_CONTENT)

    # ── Async queryset resolver ───────────────────────────────────────────────

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

    # ── Async CRUD ────────────────────────────────────────────────────────────

    async def _list_async(self, request: Request) -> Response:
        """Async mirror of list(); uses AsyncSession."""
        from lightapi.session import get_async_session

        engine = self._get_async_engine()
        pagination_cfg = self._meta.get("pagination")

        async with get_async_session(engine) as session:
            qs = await self._get_queryset_async(request)
            qs = self._run_filter_backends(request, qs)

            if pagination_cfg:
                from lightapi.pagination import CursorPaginator, PageNumberPaginator

                if pagination_cfg.style == "cursor":
                    pager = CursorPaginator()
                    rows, next_cursor = await pager.paginate_async(
                        request, qs, session, pagination_cfg.page_size
                    )
                    results = [self._serialize_row(r, "GET") for r in rows]
                    return JSONResponse(pager.wrap(results, next_cursor, None))
                else:
                    pager = PageNumberPaginator()
                    page = int(request.query_params.get("page", 1))
                    rows, total = await pager.paginate_async(
                        request, qs, session, pagination_cfg.page_size
                    )
                    results = [self._serialize_row(r, "GET") for r in rows]
                    return JSONResponse(
                        pager.wrap(
                            request, results, total, page, pagination_cfg.page_size
                        )
                    )

            instances = (await session.execute(qs)).scalars().all()
            results = [self._serialize_row(inst, "GET") for inst in instances]
            return JSONResponse({"results": results})

    async def _retrieve_async(self, request: Request, pk: int) -> Response:
        """Async mirror of retrieve(); uses AsyncSession."""
        from lightapi.session import get_async_session

        engine = self._get_async_engine()
        cls = type(self)
        async with get_async_session(engine) as session:
            instance = (
                (
                    await session.execute(
                        sa_select(cls._model_class).where(cls._model_class.id == pk)
                    )
                )
                .scalars()
                .first()
            )
            if instance is None:
                return JSONResponse(
                    {RESPONSE_KEY_DETAIL: "not found"}, status_code=HTTPStatus.NOT_FOUND
                )
            return JSONResponse(self._serialize_row(instance, "GET"))

    async def _create_async(self, data: dict[str, Any]) -> Response:
        """Async mirror of create(); ORM-style insert with flush/refresh."""
        from pydantic import ValidationError

        from lightapi.session import get_async_session

        engine = self._get_async_engine()
        cls = type(self)
        try:
            validated = cls.__schema_create__.model_validate(data)
        except ValidationError as exc:
            return JSONResponse(
                {RESPONSE_KEY_DETAIL: exc.errors()},
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )

        async with get_async_session(engine) as session:
            now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            instance = cls._model_class(
                **validated.model_dump(),
                created_at=now,
                updated_at=now,
                version=1,
            )
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            response_data = self._serialize_row(instance, "POST")
            return JSONResponse(response_data, status_code=HTTPStatus.CREATED)

    async def _update_async(
        self, data: dict[str, Any], pk: int, partial: bool = False
    ) -> Response:
        """Async mirror of update() with optimistic locking."""
        from pydantic import ValidationError

        from lightapi.session import get_async_session

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

        engine = self._get_async_engine()
        cls = type(self)

        try:
            if partial:
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

        async with get_async_session(engine) as session:
            result = await session.execute(
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
                exists = (
                    await session.execute(
                        sa_select(cls._model_class.id).where(cls._model_class.id == pk)
                    )
                ).first()
                await session.rollback()
                if not exists:
                    return JSONResponse(
                        {RESPONSE_KEY_DETAIL: "not found"},
                        status_code=HTTPStatus.NOT_FOUND,
                    )
                return JSONResponse(
                    {RESPONSE_KEY_DETAIL: "version conflict"},
                    status_code=HTTPStatus.CONFLICT,
                )
            instance = (
                (
                    await session.execute(
                        sa_select(cls._model_class).where(cls._model_class.id == pk)
                    )
                )
                .scalars()
                .first()
            )
            response_data = self._serialize_row(instance, "PUT")
            return JSONResponse(response_data)

    async def _destroy_async(self, request: Request, pk: int) -> Response:
        """Async mirror of destroy()."""
        from lightapi.session import get_async_session

        engine = self._get_async_engine()
        cls = type(self)
        async with get_async_session(engine) as session:
            stmt = (
                delete(cls._model_class)
                .where(cls._model_class.id == pk)
                .returning(cls._model_class.id)
            )
            result = (await session.execute(stmt)).first()
            if result is None:
                return JSONResponse(
                    {RESPONSE_KEY_DETAIL: "not found"}, status_code=HTTPStatus.NOT_FOUND
                )
            return Response(status_code=HTTPStatus.NO_CONTENT)
