import json
from unittest.mock import MagicMock, patch

import pytest

from lightapi.cache import BaseCache, RedisCache


class TestCache:
    def test_base_cache_get(self):
        cache = BaseCache()
        result = cache.get("test_key")
        assert result is None

    def test_base_cache_set(self):
        cache = BaseCache()
        result = cache.set("test_key", {"data": "value"}, 300)
        assert result is True

    @patch("redis.Redis")
    def test_redis_cache_init(self, mock_redis):
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        cache = RedisCache()
        mock_redis.assert_called_once_with(host="localhost", port=6379, db=0)
        assert cache.client == mock_redis_instance

    @patch("redis.Redis")
    def test_redis_cache_get_with_data(self, mock_redis):
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        cached_data = json.dumps({"test": "data"}).encode()
        mock_redis_instance.get.return_value = cached_data
        cache = RedisCache()
        result = cache.get("test_key")
        mock_redis_instance.get.assert_called_once()
        assert "test_key" in str(mock_redis_instance.get.call_args)
        assert result == {"test": "data"}

    @patch("redis.Redis")
    def test_redis_cache_get_no_data(self, mock_redis):
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.get.return_value = None
        cache = RedisCache()
        result = cache.get("test_key")
        mock_redis_instance.get.assert_called_once()
        assert result is None

    @patch("redis.Redis")
    def test_redis_cache_set(self, mock_redis):
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.setex.return_value = True
        cache = RedisCache()
        result = cache.set("test_key", {"test": "data"}, 300)
        mock_redis_instance.setex.assert_called_once()
        assert result is True
