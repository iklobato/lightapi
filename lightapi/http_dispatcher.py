"""HTTP method dispatch for LightAPI.

Provides class-based HTTP method handling using dispatch pattern.
"""

from typing import Any, Protocol

from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from lightapi.constants import HTTPStatus, RESPONSE_KEY_ALLOWED_METHODS


class HttpMethodHandler(Protocol):
    """Protocol for HTTP method handlers."""

    async def handle(self, endpoint: Any, request: Request) -> Response:
        """Handle the HTTP request."""
        ...

    def get_options_response(self, endpoint: Any, request: Request) -> Response:
        """Get the OPTIONS response for allowed methods."""
        ...


class OptionsHandler:
    """Handler for OPTIONS requests."""

    def get_options_response(self, endpoint: Any, request: Request) -> JSONResponse:
        cls = type(endpoint)
        allowed = ", ".join(sorted(cls._allowed_methods))
        return JSONResponse(
            {RESPONSE_KEY_ALLOWED_METHODS: allowed.split(", ")},
            status_code=HTTPStatus.OK,
        )


class GetHandler(HttpMethodHandler):
    """Handler for GET requests (list/retrieve)."""

    async def handle(self, endpoint: Any, request: Request) -> Response:
        pk = request.path_params.get("id")
        if pk is not None:
            return await endpoint._retrieve_async(request, pk)
        return await endpoint._list_async(request)


class GetSyncHandler(HttpMethodHandler):
    """Handler for GET sync requests."""

    async def handle(self, endpoint: Any, request: Request) -> Response:
        from lightapi.lightapi import _maybe_cached

        cls = type(endpoint)
        pk = request.path_params.get("id")
        if pk is not None:
            return endpoint.retrieve(request, pk)
        return _maybe_cached(cls, request, lambda: endpoint.list(request))

    def get_options_response(self, endpoint: Any, request: Request) -> Response:
        return OptionsHandler().get_options_response(endpoint, request)


class PostHandler(HttpMethodHandler):
    """Handler for POST requests (create)."""

    async def handle(self, endpoint: Any, request: Request) -> Response:
        from lightapi.lightapi import _read_body

        data = await _read_body(request)
        return await endpoint._create_async(data)


class PostSyncHandler(HttpMethodHandler):
    """Handler for POST sync requests."""

    async def handle(self, endpoint: Any, request: Request) -> Response:
        import asyncio
        from lightapi.lightapi import _read_body

        data = asyncio.run(_read_body(request))
        return endpoint.create(data)

    def get_options_response(self, endpoint: Any, request: Request) -> Response:
        return OptionsHandler().get_options_response(endpoint, request)


class PutHandler(HttpMethodHandler):
    """Handler for PUT requests (full update)."""

    async def handle(self, endpoint: Any, request: Request) -> Response:
        from lightapi.lightapi import _read_body

        data = await _read_body(request)
        pk = request.path_params.get("id")
        return await endpoint._update_async(request, pk, data)


class PatchHandler(HttpMethodHandler):
    """Handler for PATCH requests (partial update)."""

    async def handle(self, endpoint: Any, request: Request) -> Response:
        from lightapi.lightapi import _read_body

        data = await _read_body(request)
        pk = request.path_params.get("id")
        return await endpoint._patch_async(request, pk, data)


class DeleteHandler(HttpMethodHandler):
    """Handler for DELETE requests."""

    async def handle(self, endpoint: Any, request: Request) -> Response:
        pk = request.path_params.get("id")
        return await endpoint._delete_async(request, pk)


class HttpDispatcher:
    """Dispatcher for HTTP methods."""

    _ASYNC_HANDLERS = {
        "GET": GetHandler,
        "POST": PostHandler,
        "PUT": PutHandler,
        "PATCH": PatchHandler,
        "DELETE": DeleteHandler,
    }

    _SYNC_HANDLERS = {
        "GET": GetSyncHandler,
        "POST": PostSyncHandler,
    }

    @classmethod
    def dispatch(cls, method: str, is_async: bool) -> HttpMethodHandler:
        if is_async:
            handler_cls = cls._ASYNC_HANDLERS.get(method, OptionsHandler)
        else:
            handler_cls = cls._SYNC_HANDLERS.get(method, OptionsHandler)
        return handler_cls()

    @classmethod
    def get_options(cls, method: str, endpoint: Any, request: Request) -> Response:
        return OptionsHandler().get_options_response(endpoint, request)
