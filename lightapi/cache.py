from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional, Protocol

import redis

from lightapi.constants import DEFAULT_CACHE_TTL, DEFAULT_REDIS_URL

logger = logging.getLogger(__name__)


class CacheBackend(Protocol):
    """Protocol for cache backends."""

    def get(self, key: str) -> Optional[Dict[str, Any]]: ...
    def set(self, key: str, value: Dict[str, Any], timeout: int = 300) -> bool: ...
    def delete(self, key: str) -> bool: ...


class RedisCacheBackend:
    """Redis cache backend implementation."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or os.environ.get(
            "LIGHTAPI_REDIS_URL", DEFAULT_REDIS_URL
        )
        self._client = None

    def _get_client(self) -> Optional["redis.Redis"]:
        if self._client is None:
            try:
                self._client = redis.from_url(self._redis_url, socket_connect_timeout=1)
            except Exception:
                return None
        return self._client

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        client = self._get_client()
        if client is None:
            return None
        try:
            raw = client.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def set(self, key: str, value: Dict[str, Any], timeout: int = 300) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            client.setex(key, timeout, json.dumps(value))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            client.delete(key)
            return True
        except Exception:
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
        except Exception:
            return False

    def ping(self) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            return bool(client.ping())
        except Exception:
            return False


# Default global instance for backward compatibility
_default_backend = RedisCacheBackend()


class CacheManager:
    """Consolidated cache manager class for all cache operations.

    Provides a unified interface for caching with configurable backends.
    Supports both Redis and no-op caching.
    """

    def __init__(self, backend: Optional[CacheBackend] = None) -> None:
        """Initialize the cache manager.

        Args:
            backend: Optional cache backend. If None, uses RedisCacheBackend.
        """
        self._backend = backend or _default_backend

    def get(self, key: str) -> Any | None:
        """Retrieve cached value.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl: int = DEFAULT_CACHE_TTL) -> bool:
        """Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        return self._backend.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """Delete a cache key.

        Args:
            key: Cache key

        Returns:
            True if successful
        """
        return self._backend.delete(key)

    def invalidate_prefix(self, prefix: str) -> bool:
        """Invalidate all keys matching prefix.

        Args:
            prefix: Key prefix to match

        Returns:
            True if successful
        """
        return self._backend.invalidate_prefix(prefix)

    def ping(self) -> bool:
        """Check if cache backend is available.

        Returns:
            True if backend is reachable
        """
        return self._backend.ping()


# Global cache manager instance
_cache_manager = CacheManager()


def _get_redis() -> "redis.Redis | None":
    return _default_backend._get_client()


def _ping_redis() -> bool:
    """Return True if Redis is reachable."""
    return _default_backend.ping()


def get_cached(key: str) -> Any | None:
    """Return the cached value for *key* or None on miss / Redis failure."""
    return _default_backend.get(key)


def set_cached(key: str, value: Any, ttl: int) -> None:
    """Store *value* under *key* for *ttl* seconds. Silently ignores errors."""
    _default_backend.set(key, value, ttl)


def invalidate_cache_prefix(prefix: str) -> None:
    """Delete all keys that start with *prefix*. Silently ignores errors."""
    _default_backend.invalidate_prefix(prefix)


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
