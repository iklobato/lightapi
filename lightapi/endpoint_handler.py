"""Request handling for one RestEndpoint route."""

from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from starlette.background import BackgroundTasks
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.auth_checker import EndpointGuard
from lightapi.cache_helper import (
    invalidate_cache_after_write,
    maybe_cached,
    maybe_cached_async,
)
from lightapi.constants import RESPONSE_KEY_DETAIL, HTTPStatus
from lightapi.middleware_runner import run_post_middlewares, run_pre_middlewares
from lightapi.rest import RestEndpoint
from lightapi.session import run_blocking

if TYPE_CHECKING:
    from lightapi.authentication.base import LoginValidator


@dataclass(frozen=True)
class AppContext:
    """What every handler of one LightApi app shares."""

    middlewares: list[type]
    is_async: bool
    login_validator: LoginValidator | None = None


@dataclass(frozen=True)
class _Verb:
    """How one HTTP method is served when the user did not override it."""

    override: str
    sync_name: str
    async_name: str
    args: Callable[[Request, dict[str, Any], Any], tuple[Any, ...]]
    reads_body: bool = False
    cached: bool = False


def _request_only(request: Request, data: dict[str, Any], pk: Any) -> tuple[Any, ...]:
    return (request,)


def _data_only(request: Request, data: dict[str, Any], pk: Any) -> tuple[Any, ...]:
    return (data,)


def _request_and_pk(request: Request, data: dict[str, Any], pk: Any) -> tuple[Any, ...]:
    return (request, pk)


def _full_update(request: Request, data: dict[str, Any], pk: Any) -> tuple[Any, ...]:
    return (data, pk, False)


def _partial_update(request: Request, data: dict[str, Any], pk: Any) -> tuple[Any, ...]:
    return (data, pk, True)


_COLLECTION_VERBS = {
    "GET": _Verb("get", "list", "_list_async", _request_only, cached=True),
    "POST": _Verb("post", "create", "_create_async", _data_only, reads_body=True),
}

_DETAIL_VERBS = {
    "GET": _Verb("get", "retrieve", "_retrieve_async", _request_and_pk, cached=True),
    "PUT": _Verb("put", "update", "_update_async", _full_update, reads_body=True),
    "PATCH": _Verb(
        "patch", "update", "_update_async", _partial_update, reads_body=True
    ),
    "DELETE": _Verb("delete", "destroy", "_destroy_async", _request_and_pk),
}


class EndpointHandler:
    """Serves every request of one route (collection or detail) of an endpoint."""

    def __init__(
        self,
        endpoint_cls: type[RestEndpoint],
        verbs: dict[str, _Verb],
        app: AppContext,
    ) -> None:
        self._endpoint_cls = endpoint_cls
        self._verbs = verbs
        self._middlewares = app.middlewares
        self._is_async = app.is_async
        self._guard = EndpointGuard(
            endpoint_cls._meta.get("authentication"), app.login_validator
        )

    @classmethod
    def for_collection(
        cls, endpoint_cls: type[RestEndpoint], app: AppContext
    ) -> EndpointHandler:
        return cls(endpoint_cls, _COLLECTION_VERBS, app)

    @classmethod
    def for_detail(
        cls, endpoint_cls: type[RestEndpoint], app: AppContext
    ) -> EndpointHandler:
        return cls(endpoint_cls, _DETAIL_VERBS, app)

    @property
    def methods(self) -> list[str]:
        """HTTP methods of this route that the endpoint allows."""
        return [m for m in self._endpoint_cls._allowed_methods if m in self._verbs]

    async def handle(self, request: Request) -> Response:
        endpoint = self._endpoint_cls()
        endpoint._background = BackgroundTasks()
        endpoint._current_request = request

        pre_result = await run_pre_middlewares(self._middlewares, request)
        if pre_result is not None:
            return pre_result

        auth_result = self._guard.check(request)
        if auth_result is not None:
            return auth_result

        verb = self._verbs.get(request.method)
        if verb is None:
            result = self._method_not_allowed()
        else:
            result = await self._serve(verb, endpoint, request)

        response = JSONResponse(result) if isinstance(result, dict) else result
        await invalidate_cache_after_write(self._endpoint_cls, request)

        if endpoint._background.tasks:
            response.background = endpoint._background

        return await run_post_middlewares(self._middlewares, request, response)

    async def _serve(
        self, verb: _Verb, endpoint: RestEndpoint, request: Request
    ) -> Any:
        data = await _read_body(request) if verb.reads_body else {}
        args = verb.args(request, data, request.path_params.get("id"))

        # A column may share a verb's name (`post: str`), so only functions count.
        override = getattr(self._endpoint_cls, verb.override, None)
        if inspect.isfunction(override):
            return await self._call_override(override, endpoint, request)

        if self._is_async:
            crud_async = getattr(endpoint, verb.async_name)
            if verb.cached:
                return await maybe_cached_async(
                    self._endpoint_cls, request, lambda: crud_async(*args)
                )
            return await crud_async(*args)

        crud = getattr(endpoint, verb.sync_name)
        engine = endpoint._get_engine()
        if verb.cached:
            return await run_blocking(
                engine, maybe_cached, self._endpoint_cls, request, lambda: crud(*args)
            )
        return await run_blocking(engine, crud, *args)

    async def _call_override(
        self, override: Callable[..., Any], endpoint: RestEndpoint, request: Request
    ) -> Any:
        if asyncio.iscoroutinefunction(override):
            return await override(endpoint, request)
        if self._is_async:
            # Gives a sync override the greenlet context that endpoint.list() and
            # friends need to reach an async driver.
            return await endpoint._in_async_session(
                lambda _session: override(endpoint, request)
            )
        return await run_blocking(endpoint._get_engine(), override, endpoint, request)

    def _method_not_allowed(self) -> Response:
        allowed = ", ".join(sorted(self.methods))
        return JSONResponse(
            {RESPONSE_KEY_DETAIL: f"Method Not Allowed. Allowed: {allowed}"},
            status_code=HTTPStatus.METHOD_NOT_ALLOWED,
            headers={"Allow": allowed},
        )


async def _read_body(request: Request) -> dict[str, Any]:
    """Read and parse JSON body; return {} on failure."""
    try:
        body = await request.body()
        return json.loads(body) if body else {}
    except Exception:
        return {}
