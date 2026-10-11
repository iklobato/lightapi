from __future__ import annotations

import json
import logging
import os
from functools import cache
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional

import redis
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.constants import DEFAULT_REDIS_URL, HttpVerb

if TYPE_CHECKING:
    from lightapi.config import Cache

logger = logging.getLogger(__name__)


class RedisCacheBackend:
    """The Redis client behind ``Meta.cache``.

    Every method answers None/False when Redis cannot be reached: an endpoint
    with a cache keeps serving from the database, by design.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or os.environ.get(
            "LIGHTAPI_REDIS_URL", DEFAULT_REDIS_URL
        )
        self._client: redis.Redis | None = None

    @classmethod
    @cache
    def shared(cls) -> RedisCacheBackend:
        """The process-wide client, built on first use.

        Building it at import time fixed LIGHTAPI_REDIS_URL to whatever the
        environment held before ``import lightapi``.
        """
        return cls()

    def _get_client(self) -> redis.Redis | None:
        if self._client is None:
            try:
                self._client = redis.from_url(self._redis_url, socket_connect_timeout=1)
            except (ValueError, redis.RedisError):
                return None
        return self._client

    def get(self, key: str) -> Any | None:
        client = self._get_client()
        if client is None:
            return None
        try:
            raw = client.get(key)
            return json.loads(raw) if raw else None
        except (redis.RedisError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def set(self, key: str, value: Any, timeout: int = 300) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            client.setex(key, timeout, json.dumps(value))
            return True
        except redis.RedisError:
            return False

    def invalidate_prefix(self, prefix: str) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            keys = list(client.scan_iter(f"{prefix}*"))
            if keys:
                client.delete(*keys)
            return True
        except redis.RedisError:
            return False

    def ping(self) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            return bool(client.ping())
        except redis.RedisError:
            return False


def invalidate_cache_prefix(prefix: str) -> None:
    """Delete all keys that start with *prefix*. Silently ignores errors."""
    RedisCacheBackend.shared().invalidate_prefix(prefix)


class EndpointCache:
    """Caches and invalidates the GET responses of one RestEndpoint route.

    Built once per route. Without a ``Meta.cache`` it is a no-op: every method
    still runs fn()/checks request.method, so the handler never branches on
    whether caching is configured.
    """

    def __init__(self, endpoint_name: str, config: Cache | None) -> None:
        self._endpoint_name = endpoint_name
        self._config = config

    def serve(self, request: Request, fn: Callable[[], Response]) -> Response:
        """Serve from cache on a hit, or call fn() and populate the cache."""
        if self._config is None:
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
        if self._config is None:
            return await fn()
        cached = await run_in_threadpool(self._cached_response, request)
        if cached is not None:
            return cached
        response = await fn()
        await run_in_threadpool(self._store_response, request, response)
        return response

    async def invalidate_after_write(self, request: Request) -> None:
        """Drop this route's cached GETs after a request that may change data."""
        if request.method == HttpVerb.GET or self._config is None:
            return
        await run_in_threadpool(
            RedisCacheBackend.shared().invalidate_prefix, self._key_prefix()
        )

    def _cached_response(self, request: Request) -> Response | None:
        cached = RedisCacheBackend.shared().get(self._key(request))
        return JSONResponse(cached) if cached is not None else None

    def _store_response(self, request: Request, response: Response) -> None:
        if self._config is None or not (
            isinstance(response, JSONResponse) and response.status_code == HTTPStatus.OK
        ):
            return
        body = json.loads(response.body)
        RedisCacheBackend.shared().set(self._key(request), body, self._config.ttl)

    def _key(self, request: Request) -> str:
        query = str(request.query_params)
        return f"lightapi:{self._endpoint_name}:{request.url.path}:{query}"

    def _key_prefix(self) -> str:
        return f"lightapi:{self._endpoint_name}:"


class BaseCache:
    """
    Base class for cache implementations.

    Provides a common interface for all caching methods.
    By default, acts as a no-op cache (doesn't actually cache anything).
    """

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data from the cache.

        Args:
            key: The cache key.

        Returns:
            The cached data, or None if not found.
        """
        return None

    def set(self, key: str, value: Dict[str, Any], timeout: int = 300) -> bool:
        """
        Store data in the cache.

        Args:
            key: The cache key.
            value: The data to cache.
            timeout: The cache timeout in seconds.

        Returns:
            bool: True if the data was cached successfully, False otherwise.
        """
        return True


class RedisCache(BaseCache):
    """
    Redis-based cache implementation.

    Uses Redis for distributed caching with timeout support.
    Serializes data as JSON for storage.
    """

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        """
        Initialize a new Redis cache.

        Args:
            host: Redis server hostname.
            port: Redis server port.
            db: Redis database number.
        """
        self.client = redis.Redis(host=host, port=port, db=db)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data from the Redis cache.

        Args:
            key: The cache key.

        Returns:
            The cached data, or None if not found or if deserialization fails.
        """
        cached_data = self.client.get(key)
        if cached_data:
            try:
                return json.loads(cached_data)
            except json.JSONDecodeError:
                return None
        return None

    def set(self, key: str, value: Dict[str, Any], timeout: int = 300) -> bool:
        """
        Store data in the Redis cache.

        Args:
            key: The cache key.
            value: The data to cache.
            timeout: The cache timeout in seconds.

        Returns:
            bool: True if the data was cached successfully, False otherwise.
        """
        try:
            serialized_data = json.dumps(value)
            return self.client.setex(key, timeout, serialized_data)
        except (json.JSONDecodeError, redis.RedisError):
            return False

    def _get_cache_key(self, key: str) -> str:
        """
        Legacy support method for cache key generation.

        Args:
            key: The original cache key.

        Returns:
            str: The formatted cache key.
        """
        return key
