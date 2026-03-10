from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import redis

logger = logging.getLogger(__name__)

_REDIS_URL = os.environ.get("LIGHTAPI_REDIS_URL", "redis://localhost:6379/0")
_redis_state: dict[str, "redis.Redis | None"] = {"client": None}


def _get_redis() -> "redis.Redis | None":
    if _redis_state["client"] is None:
        try:
            _redis_state["client"] = redis.from_url(
                _REDIS_URL, socket_connect_timeout=1
            )
        except Exception:
            return None
    return _redis_state["client"]


def _ping_redis() -> bool:
    """Return True if Redis is reachable."""
    client = _get_redis()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False


def get_cached(key: str) -> Any | None:
    """Return the cached value for *key* or None on miss / Redis failure."""
    client = _get_redis()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def set_cached(key: str, value: Any, ttl: int) -> None:
    """Store *value* under *key* for *ttl* seconds. Silently ignores errors."""
    client = _get_redis()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


def invalidate_cache_prefix(prefix: str) -> None:
    """Delete all keys that start with *prefix*. Silently ignores errors."""
    client = _get_redis()
    if client is None:
        return
    try:
        keys = list(client.scan_iter(f"{prefix}*"))
        if keys:
            client.delete(*keys)
    except Exception:
        pass


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
