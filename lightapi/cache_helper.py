"""Redis-backed GET response cache for one RestEndpoint class."""

import json
from typing import Awaitable, Callable

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.cache import get_cached, invalidate_cache_prefix, set_cached


class ResponseCache:
    """Caches and invalidates GET responses of one RestEndpoint class.

    A no-op when the endpoint has no `Meta.cache`: every method still runs
    fn()/checks request.method, so callers don't need to branch on whether
    caching is configured.
    """

    def __init__(self, cls: type) -> None:
        self._cls = cls

    def serve(self, request: Request, fn: Callable[[], Response]) -> Response:
        """Serve from cache on a hit, or call fn() and populate the cache."""
        if self._cache_cfg is None:
            return fn()
        cached = self._cached_response(request)
        if cached is not None:
            return cached
        response = fn()
        self._store_response(request, response)
        return response

    async def serve_async(
        self, request: Request, fn: Callable[[], Awaitable[Response]]
    ) -> Response:
        """serve() for a coroutine; Redis calls run in a worker thread."""
        if self._cache_cfg is None:
            return await fn()
        cached = await run_in_threadpool(self._cached_response, request)
        if cached is not None:
            return cached
        response = await fn()
        await run_in_threadpool(self._store_response, request, response)
        return response

    async def invalidate_after_write(self, request: Request) -> None:
        """Drop this endpoint's cached GETs after a request that may change data."""
        if request.method == "GET" or self._cache_cfg is None:
            return
        await run_in_threadpool(invalidate_cache_prefix, self._key_prefix())

    @property
    def _cache_cfg(self):
        return self._cls._meta.get("cache")

    def _cached_response(self, request: Request) -> Response | None:
        """The cached response, or None on a miss or when Redis fails."""
        try:
            cached = get_cached(self._key(request))
        except Exception:
            return None
        return JSONResponse(cached) if cached is not None else None

    def _store_response(self, request: Request, response: Response) -> None:
        if not (isinstance(response, JSONResponse) and response.status_code == 200):
            return
        try:
            body = response.body
            if hasattr(body, "decode"):
                body = body.decode("utf-8")
            set_cached(self._key(request), json.loads(body), self._cache_cfg.ttl)
        except Exception:
            pass

    def _key(self, request: Request) -> str:
        query = str(request.query_params)
        return f"lightapi:{self._cls.__name__}:{request.url.path}:{query}"

    def _key_prefix(self) -> str:
        return f"lightapi:{self._cls.__name__}:"
