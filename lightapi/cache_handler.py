"""Cache handler for request/response caching."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.cache import get_cached, invalidate_cache_prefix, set_cached
from lightapi.constants import HTTPStatus

if TYPE_CHECKING:
    from lightapi.config import Cache


class CacheHandler:
    """Handler for HTTP cache operations.

    Provides methods for checking cached responses, storing responses in cache,
    and invalidating cache entries.
    """

    def __init__(self, cache_config: "Cache | None" = None) -> None:
        """Initialize the cache handler.

        Args:
            cache_config: Cache configuration (ttl, vary_on)
        """
        self._cache_config = cache_config

    @property
    def is_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._cache_config is not None

    def get_cached_response(
        self, request: Request, key_fn: Callable[[], str]
    ) -> JSONResponse | None:
        """Get cached response if available.

        Args:
            request: The HTTP request
            key_fn: Function to generate cache key

        Returns:
            Cached JSONResponse if found, None otherwise
        """
        if not self.is_enabled:
            return None

        key = key_fn()
        try:
            cached = get_cached(key)
        except Exception:
            cached = None

        if cached is not None:
            return JSONResponse(cached)
        return None

    def cache_response(
        self,
        request: Request,
        response: Response,
        key_fn: Callable[[], str],
    ) -> None:
        """Cache a successful response.

        Args:
            request: The HTTP request
            response: The response to cache
            key_fn: Function to generate cache key
        """
        if not self.is_enabled:
            return

        if isinstance(response, JSONResponse) and response.status_code == HTTPStatus.OK:
            key = key_fn()
            try:
                set_cached(key, json.loads(response.body), self._cache_config.ttl)
            except Exception:
                pass

    def invalidate(self, request: Request, prefix_fn: Callable[[], str]) -> None:
        """Invalidate cache entries for a prefix.

        Args:
            request: The HTTP request
            prefix_fn: Function to generate cache key prefix
        """
        if not self.is_enabled:
            return

        if request.method == "GET":
            return

        prefix = prefix_fn()
        invalidate_cache_prefix(prefix)

    @staticmethod
    def build_key(cls: type, request: Request) -> str:
        """Build a cache key from endpoint class and request.

        Args:
            cls: The endpoint class
            request: The HTTP request

        Returns:
            Cache key string
        """
        query = str(request.query_params)
        return f"lightapi:{cls.__name__}:{request.url.path}:{query}"

    @staticmethod
    def build_prefix(cls: type) -> str:
        """Build a cache key prefix from endpoint class.

        Args:
            cls: The endpoint class

        Returns:
            Cache key prefix string
        """
        return f"lightapi:{cls.__name__}:"
