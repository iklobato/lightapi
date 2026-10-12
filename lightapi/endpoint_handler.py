"""Request handling for one RestEndpoint route: middlewares, guard, verb dispatch."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum, auto
from functools import cached_property
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Final

from starlette.background import BackgroundTasks
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.cache import EndpointCache
from lightapi.constants import ApiError, ExecutionMode, HttpVerb, ResponseKey
from lightapi.rest import RestEndpoint

if TYPE_CHECKING:
    from lightapi.authentication.base import BaseAuthentication, LoginValidator
    from lightapi.config import Authentication
    from lightapi.core import Middleware


@dataclass(frozen=True)
class MiddlewareChain:
    """The app's middleware classes, run before and after every request.

    Each class is instantiated per call, as `Middleware` subclasses have always
    been, so one with state cannot leak it across requests.
    """

    classes: list[type[Middleware]]

    @cached_property
    def _awaits(self) -> dict[type[Middleware], bool]:
        """Whether each class's process() is a coroutine function; decided once."""
        return {cls: asyncio.iscoroutinefunction(cls.process) for cls in self.classes}

    async def before(self, request: Request) -> Response | None:
        """The first response a middleware answers with, or None to carry on."""
        for middleware_cls in self.classes:
            result = await self._process(middleware_cls, request, None)
            if result is not None:
                return result
        return None

    async def after(self, request: Request, response: Response) -> Response:
        """The response after every middleware saw it, last registered first."""
        for middleware_cls in reversed(self.classes):
            result = await self._process(middleware_cls, request, response)
            if result is not None:
                response = result
        return response

    async def _process(
        self, middleware_cls: type, request: Request, response: Response | None
    ) -> Response | None:
        middleware = middleware_cls()
        if self._awaits[middleware_cls]:
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
            # The backend's own 401: its text, and the challenge header its scheme
            # needs (Bearer, or Basic with a realm so browsers prompt).
            return self.backend.get_auth_error_response(request)

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
        self, request: Request, data: dict[str, Any], pk: int | None
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


@dataclass(frozen=True)
class _Override:
    """A verb method the user wrote on the endpoint (`def get(self, request)`)."""

    fn: Callable[..., Any]
    awaits: bool


@dataclass(frozen=True)
class _BoundVerb:
    """A verb resolved against one endpoint class and execution mode, at register()."""

    verb: _Verb
    crud: Callable[..., Any]  # the class's built-in CRUD function, unbound
    override: _Override | None


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
        # _meta is the endpoint's parsed Meta; the framework reads it, users set it.
        meta = endpoint_cls._meta  # noqa: SLF001
        self._cache = EndpointCache(endpoint_cls.__name__, meta.get("cache"))
        authentication = meta.get("authentication")
        self._guard = (
            EndpointGuard(authentication, app.login_validator)
            if authentication is not None
            else None
        )
        # Only the verbs the endpoint allows are bound; the others get the JSON 405.
        self._bound = {
            http_verb: self._bind(verb)
            for http_verb, verb in verbs.items()
            if http_verb.value in self.methods
        }

    def _bind(self, verb: _Verb) -> _BoundVerb:
        """Resolve what serves one verb on this endpoint class, once."""
        # A column may share a verb's name (`post: str`), so only functions count.
        candidate = getattr(self._endpoint_cls, verb.override, None)
        override = (
            _Override(candidate, asyncio.iscoroutinefunction(candidate))
            if inspect.isfunction(candidate)
            else None
        )
        crud_name = (
            verb.async_name if self._mode is ExecutionMode.ASYNC else verb.sync_name
        )
        return _BoundVerb(verb, getattr(self._endpoint_cls, crud_name), override)

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
        allowed = self._endpoint_cls._allowed_methods  # noqa: SLF001  metaclass-set
        return [verb.value for verb in self._verbs if verb.value in allowed]

    async def handle(self, request: Request) -> Response:
        endpoint = self._endpoint_cls()
        # Per-request state the handler owns on the endpoint instance.
        endpoint._background = BackgroundTasks()  # noqa: SLF001
        endpoint._current_request = request  # noqa: SLF001

        early = await self._middlewares.before(request)
        if early is not None:
            return early

        if self._guard is not None:
            denied = self._guard.check(request)
            if denied is not None:
                return denied

        http_verb = HttpVerb.of(request.method)
        bound = self._bound.get(http_verb) if http_verb is not None else None
        if bound is None:
            result = self._method_not_allowed()
        else:
            result = await self._serve(bound, endpoint, request)

        response = JSONResponse(result) if isinstance(result, dict) else result
        await self._cache.invalidate_after_write(request)

        background = endpoint._background  # noqa: SLF001  set above
        if background.tasks:
            response.background = background

        return await self._middlewares.after(request, response)

    async def _serve(
        self, bound: _BoundVerb, endpoint: RestEndpoint, request: Request
    ) -> Any:  # noqa: ANN401  a Response, or the dict an override returned
        if bound.override is not None:
            return await self._call_override(bound.override, endpoint, request)

        verb = bound.verb
        data = await self._json_body(request) if verb.reads_body else {}
        args = verb.call_arguments(request, data, request.path_params.get("id"))

        if self._mode is ExecutionMode.ASYNC:
            if verb.cached:
                return await self._cache.serve_async(
                    request, lambda: bound.crud(endpoint, *args)
                )
            return await bound.crud(endpoint, *args)

        sessions = endpoint._session_manager_or_raise()  # noqa: SLF001  plumbing
        if verb.cached:
            return await sessions.run_blocking(
                self._cache.serve, request, lambda: bound.crud(endpoint, *args)
            )
        return await sessions.run_blocking(bound.crud, endpoint, *args)

    async def _call_override(
        self, override: _Override, endpoint: RestEndpoint, request: Request
    ) -> Any:  # noqa: ANN401  whatever the override returns
        if override.awaits:
            return await override.fn(endpoint, request)
        if self._mode is ExecutionMode.ASYNC:
            # Gives a sync override the greenlet context that endpoint.list() and
            # friends need to reach an async driver.
            return await endpoint._in_async_session(  # noqa: SLF001  endpoint plumbing
                lambda _session: override.fn(endpoint, request)
            )
        sessions = endpoint._session_manager_or_raise()  # noqa: SLF001  plumbing
        return await sessions.run_blocking(override.fn, endpoint, request)

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
        return self.method_not_allowed(self.methods)

    @staticmethod
    def method_not_allowed(methods: Iterable[str]) -> JSONResponse:
        """The documented JSON 405: ``Allow`` lists the CRUD verbs, sorted.

        HEAD is left out: Starlette serves it on every GET route, and the README
        documents the Allow value as the verbs the endpoint declares.
        """
        allowed = ", ".join(sorted(m for m in methods if m != "HEAD"))
        return JSONResponse(
            {ResponseKey.DETAIL: f"Method Not Allowed. Allowed: {allowed}"},
            status_code=HTTPStatus.METHOD_NOT_ALLOWED,
            headers={"Allow": allowed},
        )
