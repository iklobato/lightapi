"""Synchronous CRUD operations for endpoints."""

import datetime
from typing import Any

from sqlalchemy import delete, update
from sqlalchemy import select as sa_select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.constants import RESPONSE_KEY_DETAIL, HTTPStatus
from lightapi.pagination import CursorPaginator, PageNumberPaginator
from lightapi.queryset import FilterRunner, QuerysetResolver, RowSerializer

_AUTO_FIELDS = frozenset({"id", "created_at", "updated_at", "version"})


class EngineResolver:
    def get(self, endpoint: Any) -> Any:
        """Get sync engine, unwrapping AsyncEngine if needed."""
        cls = type(endpoint)
        session_manager = getattr(cls, "_session_manager", None)
        if session_manager is None:
            raise RuntimeError(
                "No session_manager configured. "
                "Ensure LightApi.register() was called with a properly configured app."
            )
        engine = session_manager.engine
        try:
            from sqlalchemy.ext.asyncio import AsyncEngine as _AE

            if isinstance(engine, _AE):
                return engine.sync_engine
        except ImportError:
            pass
        return engine


class SyncCRUD:
    def __init__(self) -> None:
        self._engine_resolver = EngineResolver()
        self._queryset_resolver = QuerysetResolver()
        self._filter_runner = FilterRunner()
        self._serializer = RowSerializer()

    def list(self, endpoint: Any, request: Request) -> Response:
        """Handle GET /{path} — return collection."""
        engine = self._engine_resolver.get(endpoint)
        pagination_cfg = endpoint._meta.get("pagination")

        with Session(engine) as session:
            qs = self._queryset_resolver.get_sync(endpoint, request)
            qs = self._filter_runner.run(endpoint, request, qs)

            if pagination_cfg:
                if pagination_cfg.style == "cursor":
                    pager = CursorPaginator()
                    rows, next_cursor = pager.paginate(
                        request, qs, session, pagination_cfg.page_size
                    )
                    results = [
                        self._serializer.serialize(endpoint, r, "GET") for r in rows
                    ]
                    return JSONResponse(pager.wrap(results, next_cursor, None))
                else:
                    pager = PageNumberPaginator()
                    page = int(request.query_params.get("page", 1))
                    rows, total = pager.paginate(
                        request, qs, session, pagination_cfg.page_size
                    )
                    results = [
                        self._serializer.serialize(endpoint, r, "GET") for r in rows
                    ]
                    return JSONResponse(
                        pager.wrap(
                            request, results, total, page, pagination_cfg.page_size
                        )
                    )

            instances = session.execute(qs).scalars().all()
            results = [
                self._serializer.serialize(endpoint, inst, "GET") for inst in instances
            ]
            return JSONResponse({RESPONSE_KEY_DETAIL: results})

    def retrieve(self, endpoint: Any, request: Request, pk: int) -> Response:
        """Handle GET /{path}/{id}."""
        engine = self._engine_resolver.get(endpoint)
        cls = type(endpoint)
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
            return JSONResponse(self._serializer.serialize(endpoint, instance, "GET"))

    def create(self, endpoint: Any, data: dict[str, Any]) -> Response:
        """Handle POST /{path} — validate input and insert row."""
        from pydantic import ValidationError

        engine = self._engine_resolver.get(endpoint)
        cls = type(endpoint)
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
            session.flush()
            session.refresh(instance)
            response_data = self._serializer.serialize(endpoint, instance, "POST")
            session.commit()
            return JSONResponse(response_data, status_code=HTTPStatus.CREATED)

    def put(self, endpoint: Any, data: dict[str, Any], pk: int) -> Response:
        """Handle PUT /{path}/{id} with optimistic locking."""
        return self._do_update(endpoint, data, pk, partial=False)

    def patch(self, endpoint: Any, data: dict[str, Any], pk: int) -> Response:
        """Handle PATCH /{path}/{id} with optimistic locking."""
        return self._do_update(endpoint, data, pk, partial=True)

    def _do_update(
        self, endpoint: Any, data: dict[str, Any], pk: int, partial: bool
    ) -> Response:
        """Internal update logic for PUT/PATCH."""
        from typing import Optional as _Opt

        from pydantic import ConfigDict as _CD
        from pydantic import ValidationError
        from pydantic import create_model as _cm

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

        engine = self._engine_resolver.get(endpoint)
        cls = type(endpoint)

        try:
            if partial:
                patch_fields: dict[str, Any] = {}
                for fname, finfo in cls.__schema_create__.model_fields.items():
                    ann = finfo.annotation
                    patch_fields[fname] = (_Opt[ann], None)
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
            instance = (
                session.execute(
                    sa_select(cls._model_class).where(cls._model_class.id == pk)
                )
                .scalars()
                .first()
            )
            response_data = self._serializer.serialize(endpoint, instance, "PUT")
            session.commit()
            return JSONResponse(response_data)

    def destroy(self, endpoint: Any, request: Request, pk: int) -> Response:
        """Handle DELETE /{path}/{id}."""
        engine = self._engine_resolver.get(endpoint)
        cls = type(endpoint)
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


_crud_sync = SyncCRUD()


def sync_list(endpoint: Any, request: Request) -> Response:
    return _crud_sync.list(endpoint, request)


def sync_retrieve(endpoint: Any, request: Request, pk: int) -> Response:
    return _crud_sync.retrieve(endpoint, request, pk)


def sync_create(endpoint: Any, data: dict[str, Any]) -> Response:
    return _crud_sync.create(endpoint, data)


def sync_put(endpoint: Any, data: dict[str, Any], pk: int) -> Response:
    return _crud_sync.put(endpoint, data, pk)


def sync_patch(endpoint: Any, data: dict[str, Any], pk: int) -> Response:
    return _crud_sync.patch(endpoint, data, pk)


def sync_destroy(endpoint: Any, request: Request, pk: int) -> Response:
    return _crud_sync.destroy(endpoint, request, pk)
