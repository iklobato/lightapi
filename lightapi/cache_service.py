"""Cache service for LightAPI.

Extracts caching logic from LightApi class for better SRP.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class CacheService:
    """Handles response caching for endpoints.

    Separates caching logic from the main LightApi class.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._redis_client = None
        self._enabled = False

    @property
    def redis_url(self) -> str:
        return self._redis_url

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _get_redis(self) -> Any:
        """Get Redis client, lazily initialized."""
        if self._redis_client is not None:
            return self._redis_client

        try:
            import redis

            self._redis_client = redis.from_url(self._redis_url)
            self._enabled = True
            return self._redis_client
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self._enabled = False
            return None

    def get_cached(self, key: str) -> Optional[bytes]:
        """Get cached value by key."""
        redis_client = self._get_redis()
        if redis_client is None:
            return None

        try:
            return redis_client.get(key)
        except Exception:
            return None

    def set_cached(self, key: str, value: bytes, ttl: int) -> None:
        """Set cached value with TTL."""
        redis_client = self._get_redis()
        if redis_client is None:
            return

        try:
            redis_client.setex(key, ttl, value)
        except Exception:
            pass

    def invalidate_prefix(self, prefix: str) -> None:
        """Invalidate all keys with given prefix."""
        redis_client = self._get_redis()
        if redis_client is None:
            return

        try:
            pattern = f"{prefix}:*"
            for key in redis_client.scan_iter(match=pattern):
                redis_client.delete(key)
        except Exception:
            pass

    def maybe_wrap(
        self,
        request: Request,
        cache_config: Optional[Any],
        handler: Callable,
    ) -> Response:
        """Wrap handler with caching if configured.

        Args:
            request: The HTTP request
            cache_config: Cache configuration from endpoint Meta
            handler: The handler function to wrap

        Returns:
            Response (cached or fresh)
        """
        if cache_config is None:
            return handler()

        # Build cache key
        cache_key = f"{request.url.path}:{request.query_params}"

        # Try to get cached response
        cached = self.get_cached(cache_key)
        if cached is not None:
            import json

            try:
                data = json.loads(cached)
                return Response(content=cached, media_type="application/json")
            except json.JSONDecodeError:
                pass

        # Execute handler
        response = handler()

        # Cache successful GET responses
        if response.status_code == 200:
            self.set_cached(cache_key, response.body, cache_config.ttl)

        return response

    def check_connections(self) -> bool:
        """Check if Redis is available.

        Returns:
            True if Redis is available, False otherwise
        """
        redis_client = self._get_redis()
        if redis_client is None:
            return False

        try:
            redis_client.ping()
            return True
        except Exception:
            return False
