"""Cache helper functions for GET caching and cache invalidation."""

import json
from typing import Awaitable, Callable

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.cache import get_cached, invalidate_cache_prefix, set_cached


def maybe_cached(cls: type, request: Request, fn: Callable[[], Response]) -> Response:
    """Serve from Redis cache (GET only) or call fn() and populate cache."""
    if cls._meta.get("cache") is None:
        return fn()
    cached = _cached_response(cls, request)
    if cached is not None:
        return cached
    response = fn()
    _store_response(cls, request, response)
    return response


async def maybe_cached_async(
    cls: type, request: Request, fn: Callable[[], Awaitable[Response]]
) -> Response:
    """maybe_cached() for a coroutine; Redis calls run in a worker thread."""
    if cls._meta.get("cache") is None:
        return await fn()
    cached = await run_in_threadpool(_cached_response, cls, request)
    if cached is not None:
        return cached
    response = await fn()
    await run_in_threadpool(_store_response, cls, request, response)
    return response


async def invalidate_cache_after_write(cls: type, request: Request) -> None:
    """Drop the endpoint's cached GETs after a request that may have changed data."""
    if request.method == "GET" or cls._meta.get("cache") is None:
        return
    await run_in_threadpool(invalidate_cache_prefix, _cache_key_prefix(cls))


def _cached_response(cls: type, request: Request) -> Response | None:
    """The cached response, or None on a miss or when Redis fails."""
    try:
        cached = get_cached(_cache_key(cls, request))
    except Exception:
        return None
    return JSONResponse(cached) if cached is not None else None


def _store_response(cls: type, request: Request, response: Response) -> None:
    if not (isinstance(response, JSONResponse) and response.status_code == 200):
        return
    try:
        body = response.body
        if hasattr(body, "decode"):
            body = body.decode("utf-8")
        set_cached(_cache_key(cls, request), json.loads(body), cls._meta["cache"].ttl)
    except Exception:
        pass


def _cache_key(cls: type, request: Request) -> str:
    query = str(request.query_params)
    return f"lightapi:{cls.__name__}:{request.url.path}:{query}"


def _cache_key_prefix(cls: type) -> str:
    return f"lightapi:{cls.__name__}:"
