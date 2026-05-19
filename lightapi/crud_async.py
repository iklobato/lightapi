"""Asynchronous CRUD operations for endpoints."""

import datetime
from typing import Any

from sqlalchemy import delete, update
from sqlalchemy import select as sa_select
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.constants import RESPONSE_KEY_DETAIL, HTTPStatus
from lightapi.pagination import CursorPaginator, PageNumberPaginator
from lightapi.queryset import FilterRunner, QuerysetResolver, RowSerializer
from lightapi.session import get_async_session

_AUTO_FIELDS = frozenset({"id", "created_at", "updated_at", "version"})


class AsyncEngineResolver:
    def get(self, endpoint: Any) -> Any:
        """Get async engine for async session creation."""
        cls = type(endpoint)
        session_manager = getattr(cls, "_session_manager", None)
        if session_manager is None:
            raise RuntimeError(
                "No session_manager configured. "
                "Ensure LightApi.register() was called with a properly configured app."
            )
        return session_manager.engine


class AsyncCRUD:
    def __init__(self) -> None:
        self._engine_resolver = AsyncEngineResolver()
        self._queryset_resolver = QuerysetResolver()
        self._filter_runner = FilterRunner()
        self._serializer = RowSerializer()

    async def list(self, endpoint: Any, request: Request) -> Response:
        """Async: Handle GET /{path} — return collection."""
        engine = self._engine_resolver.get(endpoint)
        pagination_cfg = endpoint._meta.get("pagination")

        async with get_async_session(engine) as session:
            qs = await self._queryset_resolver.get_async(endpoint, request)
            qs = self._filter_runner.run(endpoint, request, qs)

            if pagination_cfg:
                if pagination_cfg.style == "cursor":
                    pager = CursorPaginator()
                    rows, next_cursor = await pager.paginate_async(
                        request, qs, session, pagination_cfg.page_size
                    )
                    results = [
                        self._serializer.serialize(endpoint, r, "GET") for r in rows
                    ]
                    return JSONResponse(pager.wrap(results, next_cursor, None))
                else:
                    pager = PageNumberPaginator()
                    page = int(request.query_params.get("page", 1))
                    rows, total = await pager.paginate_async(
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

            instances = (await session.execute(qs)).scalars().all()
            results = [
                self._serializer.serialize(endpoint, inst, "GET") for inst in instances
            ]
            return JSONResponse({RESPONSE_KEY_DETAIL: results})

    async def retrieve(self, endpoint: Any, request: Request, pk: int) -> Response:
        """Async: Handle GET /{path}/{id}."""
        engine = self._engine_resolver.get(endpoint)
        cls = type(endpoint)
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
            return JSONResponse(self._serializer.serialize(endpoint, instance, "GET"))

    async def create(self, endpoint: Any, data: dict[str, Any]) -> Response:
        """Async: Handle POST /{path} — validate input and insert row."""
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
            response_data = self._serializer.serialize(endpoint, instance, "POST")
            return JSONResponse(response_data, status_code=HTTPStatus.CREATED)

    async def put(self, endpoint: Any, data: dict[str, Any], pk: int) -> Response:
        """Async: Handle PUT /{path}/{id} with optimistic locking."""
        return await self._do_update(endpoint, data, pk, partial=False)

    async def patch(self, endpoint: Any, data: dict[str, Any], pk: int) -> Response:
        """Async: Handle PATCH /{path}/{id} with optimistic locking."""
        return await self._do_update(endpoint, data, pk, partial=True)

    async def _do_update(
        self, endpoint: Any, data: dict[str, Any], pk: int, partial: bool
    ) -> Response:
        """Internal async update logic for PUT/PATCH."""
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
                exists = await session.execute(
                    sa_select(cls._model_class.id).where(cls._model_class.id == pk)
                )
                await session.rollback()
                if not exists.first():
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
            response_data = self._serializer.serialize(endpoint, instance, "PUT")
            return JSONResponse(response_data)

    async def destroy(self, endpoint: Any, request: Request, pk: int) -> Response:
        """Async: Handle DELETE /{path}/{id}."""
        engine = self._engine_resolver.get(endpoint)
        cls = type(endpoint)
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


_crud_async = AsyncCRUD()


async def async_list(endpoint: Any, request: Request) -> Response:
    return await _crud_async.list(endpoint, request)


async def async_retrieve(endpoint: Any, request: Request, pk: int) -> Response:
    return await _crud_async.retrieve(endpoint, request, pk)


async def async_create(endpoint: Any, data: dict[str, Any]) -> Response:
    return await _crud_async.create(endpoint, data)


async def async_put(endpoint: Any, data: dict[str, Any], pk: int) -> Response:
    return await _crud_async.put(endpoint, data, pk)


async def async_patch(endpoint: Any, data: dict[str, Any], pk: int) -> Response:
    return await _crud_async.patch(endpoint, data, pk)


async def async_destroy(endpoint: Any, request: Request, pk: int) -> Response:
    return await _crud_async.destroy(endpoint, request, pk)
