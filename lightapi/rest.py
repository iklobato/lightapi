"""RestEndpointMeta metaclass and RestEndpoint base class."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any, get_args, get_origin
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    delete,
    insert,
    select as sa_select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

try:
    from sqlalchemy import Uuid as SAUuid  # SQLAlchemy 2.0+
except ImportError:
    SAUuid = None  # type: ignore[assignment,misc]

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.exceptions import ConfigurationError, SerializationError
from lightapi.schema import (
    SchemaFactory,
    _apply_fields,
    _row_to_dict,
    normalise_serializer,
    resolve_fields,
)

_AUTO_FIELDS = frozenset({"id", "created_at", "updated_at", "version"})

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
    """Metaclass that turns annotated RestEndpoint subclasses into mapped SQLAlchemy tables."""

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

        is_base_only = kwargs.get("base_only", False) or namespace.get("_base_only", False)
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

        from lightapi.fields import _LIGHTAPI_KWARGS
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
            Column("updated_at", DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow),
            Column("version", Integer, default=1, nullable=False),
        ]

        # ── Step 4: SchemaFactory ─────────────────────────────────────────────
        cls.__schema_create__, cls.__schema_read__ = SchemaFactory.build(cls)  # type: ignore[attr-defined]

        # ── Step 5: Parse Meta → _meta ────────────────────────────────────────
        meta_obj = namespace.get("Meta") or getattr(cls, "Meta", None)
        raw_serializer = getattr(meta_obj, "serializer", None) if meta_obj else None

        # Guard: Meta.serializer must be Serializer instance/subclass
        if raw_serializer is not None:
            from pydantic import BaseModel as PydanticBaseModel
            if isinstance(raw_serializer, type):
                if issubclass(raw_serializer, PydanticBaseModel):
                    raise ConfigurationError(
                        f"Meta.serializer on '{name}' must be a Serializer instance or subclass, "
                        f"not a BaseModel subclass."
                    )
        serialiser_normalised = normalise_serializer(raw_serializer)

        cls._meta = {  # type: ignore[attr-defined]
            "authentication": getattr(meta_obj, "authentication", None) if meta_obj else None,
            "filtering": getattr(meta_obj, "filtering", None) if meta_obj else None,
            "pagination": getattr(meta_obj, "pagination", None) if meta_obj else None,
            "serializer_normalised": serialiser_normalised,
            "cache": getattr(meta_obj, "cache", None) if meta_obj else None,
            "reflect": getattr(meta_obj, "reflect", False) if meta_obj else False,
            "table": getattr(meta_obj, "table", None) if meta_obj else None,
        }
        cls._fields_info = fields_info  # type: ignore[attr-defined]

        # ── Step 6: MRO scan for HttpMethod markers ───────────────────────────
        from lightapi.methods import HttpMethod

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
            _map_imperatively(cls, name, all_columns=auto_cols + columns, meta_obj=meta_obj)

    def __init__(cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(name, bases, namespace, **kwargs)


def _map_imperatively(
    cls: type,
    name: str,
    all_columns: list[Column],
    meta_obj: Any,
) -> None:
    """Register the class as a SQLAlchemy mapped entity using the app-level registry."""
    from lightapi._registry import get_registry_and_metadata
    from pydantic.fields import FieldInfo

    registry, metadata = get_registry_and_metadata()

    table_name = (
        getattr(meta_obj, "table", None)
        or f"{name.lower()}s"
    )

    # Avoid double-mapping (e.g., when class is referenced from two routes)
    try:
        from sqlalchemy import inspect as sa_inspect
        sa_inspect(cls)
        cls._model_class = cls  # type: ignore[attr-defined]
        return
    except Exception:
        pass

    # Remove FieldInfo class attributes so SQLAlchemy can instrument them.
    # We already saved them in cls._fields_info; restore as plain defaults after mapping.
    stashed: dict[str, Any] = {}
    for col in all_columns:
        existing = cls.__dict__.get(col.name)
        if isinstance(existing, FieldInfo):
            stashed[col.name] = existing
            try:
                delattr(cls, col.name)
            except AttributeError:
                pass

    if table_name in metadata.tables:
        table = Table(table_name, metadata, *all_columns, extend_existing=True)
    else:
        table = Table(table_name, metadata, *all_columns)
    registry.map_imperatively(cls, table)
    cls._model_class = cls  # type: ignore[attr-defined]


def _map_reflected(
    cls: type,
    name: str,
    meta_obj: Any,
    partial: bool,
    extra_columns: list[Column] | None = None,
) -> None:
    """Map a RestEndpoint to an existing database table via reflection.

    partial=False → pure reflection; no new columns added.
    partial=True  → reflect existing table then add extra_columns from user annotations.
    """
    from lightapi._registry import get_engine, get_registry_and_metadata
    from sqlalchemy import inspect as sa_inspect_engine

    registry, metadata = get_registry_and_metadata()
    engine = get_engine()

    table_name = getattr(meta_obj, "table", None) or f"{name.lower()}s"

    existing_inspector = sa_inspect_engine(engine)
    if table_name not in existing_inspector.get_table_names():
        raise ConfigurationError(
            f"Meta.reflect is set on '{name}' but table '{table_name}' "
            "does not exist in the database."
        )

    if table_name not in metadata.tables:
        # Reflect the table into our metadata
        from sqlalchemy import Table
        table = Table(table_name, metadata, autoload_with=engine)
    else:
        table = metadata.tables[table_name]

    if partial and extra_columns:
        for col in extra_columns:
            if col.name not in table.c:
                table.append_column(col)

    try:
        from sqlalchemy import inspect as sa_inspect
        sa_inspect(cls)
        cls._model_class = cls  # type: ignore[attr-defined]
        return
    except Exception:
        pass

    registry.map_imperatively(cls, table)
    cls._model_class = cls  # type: ignore[attr-defined]


class Validator:
    """Backward-compatibility stub. Use Pydantic Field constraints instead."""


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
        for k, v in kwargs.items():
            setattr(self, k, v)

    # ── CRUD helpers ──────────────────────────────────────────────────────────

    def _get_engine(self) -> Any:
        from lightapi._registry import get_engine
        return get_engine()

    def _get_queryset(self, request: Request) -> Any:
        cls = type(self)
        qs_attr = cls.__dict__.get("queryset") or getattr(cls, "queryset", None)
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
        cls = type(self)
        pagination_cfg = self._meta.get("pagination")

        with Session(engine) as session:
            qs = self._get_queryset(request)
            qs = self._run_filter_backends(request, qs)

            if pagination_cfg:
                from lightapi.pagination import CursorPaginator, PageNumberPaginator

                if pagination_cfg.style == "cursor":
                    pager = CursorPaginator()
                    rows, next_cursor = pager.paginate(request, qs, session, pagination_cfg.page_size)
                    results = [self._serialize_row(r, "GET") for r in rows]
                    return JSONResponse(pager.wrap(results, next_cursor, None))
                else:
                    pager = PageNumberPaginator()
                    page = int(request.query_params.get("page", 1))
                    rows, total = pager.paginate(request, qs, session, pagination_cfg.page_size)
                    results = [self._serialize_row(r, "GET") for r in rows]
                    return JSONResponse(pager.wrap(request, results, total, page, pagination_cfg.page_size))

            instances = session.execute(qs).scalars().all()
            results = [self._serialize_row(inst, "GET") for inst in instances]
            return JSONResponse({"results": results})

    def retrieve(self, request: Request, pk: int) -> Response:
        """Handle GET /{path}/{id}."""
        from sqlalchemy.orm import Session

        engine = self._get_engine()
        cls = type(self)
        with Session(engine) as session:
            instance = session.execute(
                sa_select(cls._model_class).where(cls._model_class.id == pk)
            ).scalars().first()
            if instance is None:
                return JSONResponse({"detail": "not found"}, status_code=404)
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
            return JSONResponse({"detail": exc.errors()}, status_code=422)

        with Session(engine) as session:
            now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            instance = cls._model_class(
                **validated.model_dump(),
                created_at=now,
                updated_at=now,
                version=1,
            )
            session.add(instance)
            session.flush()          # executes INSERT, populates auto-increment id
            session.refresh(instance)  # re-loads all columns (including DB-generated ones)
            response_data = self._serialize_row(instance, "POST")
            session.commit()
            return JSONResponse(response_data, status_code=201)

    def update(self, data: dict[str, Any], pk: int, partial: bool = False) -> Response:
        """Handle PUT/PATCH /{path}/{id} with optimistic locking."""
        from pydantic import ValidationError
        from sqlalchemy.orm import Session

        client_version = data.get("version")
        if client_version is None:
            return JSONResponse(
                {"detail": [{"loc": ["version"], "msg": "Field required", "type": "missing"}]},
                status_code=422,
            )

        engine = self._get_engine()
        cls = type(self)

        try:
            if partial:
                # Build a one-shot model where every field is Optional so that
                # PATCH can supply any subset of fields without validation errors.
                from typing import Optional as _Opt
                from pydantic import create_model as _cm, ConfigDict as _CD
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
                update_data = {
                    k: v
                    for k, v in validated.model_dump(exclude_unset=True).items()
                    if k not in _AUTO_FIELDS and v is not None
                }
            else:
                validated = cls.__schema_create__.model_validate(data)
                update_data = {
                    k: v for k, v in validated.model_dump().items() if k not in _AUTO_FIELDS
                }
        except ValidationError as exc:
            return JSONResponse({"detail": exc.errors()}, status_code=422)

        update_data.pop("version", None)

        with Session(engine) as session:
            result = session.execute(
                update(cls._model_class)
                .where(
                    cls._model_class.id == pk,
                    cls._model_class.version == client_version,
                )
                .values(**update_data, version=client_version + 1,
                        updated_at=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))
            )
            if result.rowcount == 0:
                exists = session.execute(
                    sa_select(cls._model_class.id).where(cls._model_class.id == pk)
                ).first()
                session.rollback()
                if not exists:
                    return JSONResponse({"detail": "not found"}, status_code=404)
                return JSONResponse({"detail": "version conflict"}, status_code=409)
            # Re-fetch so all columns (including updated_at/version) are current
            instance = session.execute(
                sa_select(cls._model_class).where(cls._model_class.id == pk)
            ).scalars().first()
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
                return JSONResponse({"detail": "not found"}, status_code=404)
            session.commit()
            return Response(status_code=204)
