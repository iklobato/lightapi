import hashlib
import json
from typing import Any, Dict, Optional

import redis


class BaseCache:
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return None

    def set(self, key: str, value: Dict[str, Any], timeout: int = 300) -> bool:
        return True


class RedisCache(BaseCache):
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.client = redis.Redis(host=host, port=port, db=db)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        cache_key = self._get_cache_key(key)
        cached_data = self.client.get(cache_key)
        if cached_data:
            try:
                return json.loads(cached_data)
            except json.JSONDecodeError:
                return None
        return None

    def set(self, key: str, value: Dict[str, Any], timeout: int = 300) -> bool:
        cache_key = self._get_cache_key(key)
        try:
            serialized_data = json.dumps(value)
            return self.client.setex(cache_key, timeout, serialized_data)
        except (json.JSONDecodeError, redis.RedisError):
            return False

    def _get_cache_key(self, key: str) -> str:
        return f"lightapi:{hashlib.md5(key.encode()).hexdigest()}"
