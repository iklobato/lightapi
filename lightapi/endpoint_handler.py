"""Request handling for one RestEndpoint route: middlewares, guard, verb dispatch."""

from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass
from enum import Enum, auto
from functools import cached_property
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Callable, Final

from starlette.background import BackgroundTasks
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.cache import EndpointCache
from lightapi.constants import ApiError, ExecutionMode, HttpVerb, ResponseKey
from lightapi.rest import RestEndpoint

if TYPE_CHECKING:
    from lightapi.authentication.base import BaseAuthentication, LoginValidator
    from lightapi.config import Authentication


@dataclass(frozen=True)
class MiddlewareChain:
    """The app's middleware classes, run before and after every request.

    Each class is instantiated per call, as `Middleware` subclasses have always
    been, so one with state cannot leak it across requests.
    """

    classes: list[type]

    async def before(self, request: Request) -> Response | None:
        """The first response a middleware answers with, or None to carry on."""
        for middleware_cls in self.classes:
            result = await self._process(middleware_cls(), request, None)
            if result is not None:
                return result
        return None

    async def after(self, request: Request, response: Response) -> Response:
        """The response after every middleware saw it, last registered first."""
        for middleware_cls in reversed(self.classes):
            result = await self._process(middleware_cls(), request, response)
            if result is not None:
                response = result
        return response

    @staticmethod
    async def _process(
        middleware: Any, request: Request, response: Response | None
    ) -> Response | None:
        if asyncio.iscoroutinefunction(middleware.process):
            awaited: Response | None = await middleware.process(request, response)
            return awaited
        result: Response | None = middleware.process(request, response)
        return result


@dataclass(frozen=True)
class AppContext:
    """What every handler of one LightApi app shares."""

    middlewares: MiddlewareChain
    mode: ExecutionMode
    login_validator: LoginValidator | None = None


class EndpointGuard:
    """Decides whether a request may reach an endpoint with an Authentication."""

    def __init__(
        self,
        authentication: Authentication,
        login_validator: LoginValidator | None = None,
    ) -> None:
        self._authentication = authentication
        self._login_validator = login_validator

    @cached_property
    def backend(self) -> BaseAuthentication:
        """Built on the first request that needs it, then shared by every later one."""
        return self._authentication.build_backend(self._login_validator)

    def check(self, request: Request) -> Response | None:
        """The 401 or 403 response that stops the request, or None to let it in."""
        authentication = self._authentication
        if authentication.requires_login(request.method) and not (
            self.backend.authenticate(request)
        ):
            return ApiError.AUTHENTICATION_REQUIRED.response()

        permission = authentication.permission_for(request.method)
        if permission is not None and not permission().has_permission(request):
            return ApiError.INSUFFICIENT_PERMISSIONS.response()

        return None


class _CrudArgument(Enum):
    """One positional argument of a built-in CRUD method."""

    REQUEST = auto()
    DATA = auto()
    PK = auto()
    FULL_UPDATE = auto()
    PARTIAL_UPDATE = auto()


@dataclass(frozen=True)
class _Verb:
    """How one HTTP method is served when the user did not override it."""

    override: str
    sync_name: str
    async_name: str
    arguments: tuple[_CrudArgument, ...]
    reads_body: bool = False
    cached: bool = False

    def call_arguments(
        self, request: Request, data: dict[str, Any], pk: Any
    ) -> tuple[Any, ...]:
        values: dict[_CrudArgument, Any] = {
            _CrudArgument.REQUEST: request,
            _CrudArgument.DATA: data,
            _CrudArgument.PK: pk,
            _CrudArgument.FULL_UPDATE: False,
            _CrudArgument.PARTIAL_UPDATE: True,
        }
        return tuple(values[argument] for argument in self.arguments)


_COLLECTION_VERBS: Final[dict[HttpVerb, _Verb]] = {
    HttpVerb.GET: _Verb(
        "get", "list", "_list_async", (_CrudArgument.REQUEST,), cached=True
    ),
    HttpVerb.POST: _Verb(
        "post", "create", "_create_async", (_CrudArgument.DATA,), reads_body=True
    ),
}

_DETAIL_VERBS: Final[dict[HttpVerb, _Verb]] = {
    HttpVerb.GET: _Verb(
        "get",
        "retrieve",
        "_retrieve_async",
        (_CrudArgument.REQUEST, _CrudArgument.PK),
        cached=True,
    ),
    HttpVerb.PUT: _Verb(
        "put",
        "update",
        "_update_async",
        (_CrudArgument.DATA, _CrudArgument.PK, _CrudArgument.FULL_UPDATE),
        reads_body=True,
    ),
    HttpVerb.PATCH: _Verb(
        "patch",
        "update",
        "_update_async",
        (_CrudArgument.DATA, _CrudArgument.PK, _CrudArgument.PARTIAL_UPDATE),
        reads_body=True,
    ),
    HttpVerb.DELETE: _Verb(
        "delete",
        "destroy",
        "_destroy_async",
        (_CrudArgument.REQUEST, _CrudArgument.PK),
    ),
}


class EndpointHandler:
    """Serves every request of one route (collection or detail) of an endpoint."""

    def __init__(
        self,
        endpoint_cls: type[RestEndpoint],
        verbs: dict[HttpVerb, _Verb],
        app: AppContext,
    ) -> None:
        self._endpoint_cls = endpoint_cls
        self._verbs = verbs
        self._middlewares = app.middlewares
        self._mode = app.mode
        self._cache = EndpointCache(
            endpoint_cls.__name__, endpoint_cls._meta.get("cache")
        )
        authentication = endpoint_cls._meta.get("authentication")
        self._guard = (
            EndpointGuard(authentication, app.login_validator)
            if authentication is not None
            else None
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
        allowed = self._endpoint_cls._allowed_methods
        return [verb.value for verb in self._verbs if verb.value in allowed]

    async def handle(self, request: Request) -> Response:
        endpoint = self._endpoint_cls()
        endpoint._background = BackgroundTasks()
        endpoint._current_request = request

        early = await self._middlewares.before(request)
        if early is not None:
            return early

        if self._guard is not None:
            denied = self._guard.check(request)
            if denied is not None:
                return denied

        http_verb = HttpVerb.of(request.method)
        verb = self._verbs.get(http_verb) if http_verb is not None else None
        if verb is None:
            result = self._method_not_allowed()
        else:
            result = await self._serve(verb, endpoint, request)

        response = JSONResponse(result) if isinstance(result, dict) else result
        await self._cache.invalidate_after_write(request)

        if endpoint._background.tasks:
            response.background = endpoint._background

        return await self._middlewares.after(request, response)

    async def _serve(
        self, verb: _Verb, endpoint: RestEndpoint, request: Request
    ) -> Any:
        data = await self._json_body(request) if verb.reads_body else {}
        args = verb.call_arguments(request, data, request.path_params.get("id"))

        # A column may share a verb's name (`post: str`), so only functions count.
        override = getattr(self._endpoint_cls, verb.override, None)
        if inspect.isfunction(override):
            return await self._call_override(override, endpoint, request)

        if self._mode is ExecutionMode.ASYNC:
            crud_async = getattr(endpoint, verb.async_name)
            if verb.cached:
                return await self._cache.serve_async(request, lambda: crud_async(*args))
            return await crud_async(*args)

        crud = getattr(endpoint, verb.sync_name)
        sessions = endpoint._session_manager_or_raise()
        if verb.cached:
            return await sessions.run_blocking(
                self._cache.serve, request, lambda: crud(*args)
            )
        return await sessions.run_blocking(crud, *args)

    async def _call_override(
        self, override: Callable[..., Any], endpoint: RestEndpoint, request: Request
    ) -> Any:
        if asyncio.iscoroutinefunction(override):
            return await override(endpoint, request)
        if self._mode is ExecutionMode.ASYNC:
            # Gives a sync override the greenlet context that endpoint.list() and
            # friends need to reach an async driver.
            return await endpoint._in_async_session(
                lambda _session: override(endpoint, request)
            )
        return await endpoint._session_manager_or_raise().run_blocking(
            override, endpoint, request
        )

    @staticmethod
    async def _json_body(request: Request) -> dict[str, Any]:
        """The JSON body as sent; {} when empty or not JSON, so validation reports it.

        Anything else (a dropped connection, a consumed stream) propagates.
        """
        try:
            body: dict[str, Any] = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
        return body

    def _method_not_allowed(self) -> Response:
        allowed = ", ".join(sorted(self.methods))
        return JSONResponse(
            {ResponseKey.DETAIL: f"Method Not Allowed. Allowed: {allowed}"},
            status_code=HTTPStatus.METHOD_NOT_ALLOWED,
            headers={"Allow": allowed},
        )
