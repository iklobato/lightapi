"""Cache helper functions for GET caching and cache invalidation."""

import json
from typing import Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.cache import get_cached, invalidate_cache_prefix, set_cached


def maybe_cached(cls: type, request: Request, fn: Callable[[], Response]) -> Response:
    """Serve from Redis cache (GET only) or call fn() and populate cache."""
    cache_cfg = cls._meta.get("cache")
    if cache_cfg is None:
        return fn()

    key = _cache_key(cls, request)
    try:
        cached = get_cached(key)
    except Exception:
        cached = None
    if cached is not None:
        return JSONResponse(cached)
    response = fn()
    if isinstance(response, JSONResponse) and response.status_code == 200:
        try:
            body = response.body
            if hasattr(body, "decode"):
                body = body.decode("utf-8")
            set_cached(key, json.loads(body), cache_cfg.ttl)
        except Exception:
            pass
    return response


def maybe_invalidate_cache(cls: type, request: Request) -> None:
    """Invalidate cache entries after mutating requests."""
    if request.method == "GET":
        return
    cache_cfg = cls._meta.get("cache")
    if cache_cfg is None:
        return

    invalidate_cache_prefix(_cache_key_prefix(cls))


def _cache_key(cls: type, request: Request) -> str:
    query = str(request.query_params)
    return f"lightapi:{cls.__name__}:{request.url.path}:{query}"


def _cache_key_prefix(cls: type) -> str:
    return f"lightapi:{cls.__name__}:"
