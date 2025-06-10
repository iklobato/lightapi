import hashlib
import json
from typing import Any, Dict, Optional

import redis


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
