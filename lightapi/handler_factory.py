"""Handler factory for creating Starlette route handlers."""

from typing import Any

import asyncio
from starlette.background import BackgroundTasks
from starlette.requests import Request
from starlette.responses import Response

from lightapi.constants import HTTPStatus, RESPONSE_KEY_DETAIL
from lightapi.rest import RestEndpoint


def make_collection_handler(
    cls: type[RestEndpoint],
    middlewares: list[type],
    is_async: bool,
) -> Any:
    """Create collection endpoint handler (list/create)."""

    async def handler(request: Request) -> Response:
        from lightapi.auth_checker import check_auth
        from lightapi.body_reader import read_body
        from lightapi.middleware_runner import run_post_middlewares, run_pre_middlewares
        from lightapi.response_wrapper import wrap_dict_response

        endpoint = cls()
        endpoint._background = BackgroundTasks()
        endpoint._current_request = request

        pre_result = await run_pre_middlewares(middlewares, request)
        if pre_result is not None:
            return pre_result

        auth_result = check_auth(cls, request)
        if auth_result is not None:
            return auth_result

        if request.method == "GET":
            get_override = getattr(cls, "get", None)
            if get_override and asyncio.iscoroutinefunction(get_override):
                result = await get_override(endpoint, request)
            elif is_async:
                result = await endpoint._list_async(request)
            else:
                from lightapi.cache_helper import maybe_cached

                result = maybe_cached(cls, request, lambda: endpoint.list(request))
        elif request.method == "POST":
            data = await read_body(request)
            post_override = getattr(cls, "post", None)
            if post_override and asyncio.iscoroutinefunction(post_override):
                result = await post_override(endpoint, request)
            elif is_async:
                result = await endpoint._create_async(data)
            else:
                result = endpoint.create(data)
        else:
            allowed = ", ".join(sorted(cls._allowed_methods & {"GET", "POST"}))
            result = __import__(
                "starlette.responses", fromlist=["JSONResponse"]
            ).JSONResponse(
                {RESPONSE_KEY_DETAIL: f"Method Not Allowed. Allowed: {allowed}"},
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                headers={"Allow": allowed},
            )

        response = wrap_dict_response(result)

        if not is_async:
            from lightapi.cache_helper import maybe_invalidate_cache

            maybe_invalidate_cache(cls, request)

        if endpoint._background.tasks:
            response.background = endpoint._background

        return await run_post_middlewares(middlewares, request, response)

    handler.__name__ = f"{cls.__name__}_collection"
    handler.__endpoint_cls__ = cls
    return handler


def make_detail_handler(
    cls: type[RestEndpoint],
    middlewares: list[type],
    is_async: bool,
) -> Any:
    """Create detail endpoint handler (retrieve/update/delete)."""

    async def handler(request: Request) -> Response:
        from lightapi.auth_checker import check_auth
        from lightapi.body_reader import read_body
        from lightapi.middleware_runner import run_post_middlewares, run_pre_middlewares
        from lightapi.response_wrapper import wrap_dict_response

        pk: int = request.path_params["id"]
        endpoint = cls()
        endpoint._background = BackgroundTasks()
        endpoint._current_request = request

        pre_result = await run_pre_middlewares(middlewares, request)
        if pre_result is not None:
            return pre_result

        auth_result = check_auth(cls, request)
        if auth_result is not None:
            return auth_result

        if request.method == "GET":
            get_override = getattr(cls, "get", None)
            if get_override and asyncio.iscoroutinefunction(get_override):
                result = await get_override(endpoint, request)
            elif is_async:
                result = await endpoint._retrieve_async(request, pk)
            else:
                from lightapi.cache_helper import maybe_cached

                result = maybe_cached(
                    cls, request, lambda: endpoint.retrieve(request, pk)
                )
        elif request.method in {"PUT", "PATCH"}:
            data = await read_body(request)
            partial = request.method == "PATCH"
            put_override = getattr(cls, "put" if not partial else "patch", None)
            if put_override and asyncio.iscoroutinefunction(put_override):
                result = await put_override(endpoint, request)
            elif is_async:
                result = await endpoint._update_async(data, pk, partial=partial)
            else:
                result = endpoint.update(data, pk, partial=partial)
        elif request.method == "DELETE":
            delete_override = getattr(cls, "delete", None)
            if delete_override and asyncio.iscoroutinefunction(delete_override):
                result = await delete_override(endpoint, request)
            elif is_async:
                result = await endpoint._destroy_async(request, pk)
            else:
                result = endpoint.destroy(request, pk)
        else:
            allowed = ", ".join(
                sorted(cls._allowed_methods & {"GET", "PUT", "PATCH", "DELETE"})
            )
            result = __import__(
                "starlette.responses", fromlist=["JSONResponse"]
            ).JSONResponse(
                {RESPONSE_KEY_DETAIL: f"Method Not Allowed. Allowed: {allowed}"},
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                headers={"Allow": allowed},
            )

        response = wrap_dict_response(result)

        if not is_async:
            from lightapi.cache_helper import maybe_invalidate_cache

            maybe_invalidate_cache(cls, request)

        if endpoint._background.tasks:
            response.background = endpoint._background

        return await run_post_middlewares(middlewares, request, response)

    handler.__name__ = f"{cls.__name__}_detail"
    handler.__endpoint_cls__ = cls
    return handler
