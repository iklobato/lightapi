"""The process-wide Redis client is created on first use, not at import time."""

from unittest.mock import patch

import pytest

from lightapi import cache
from lightapi.cache import RedisCacheBackend

LATE_URL = "redis://configured-after-import:6379/3"


@pytest.fixture(autouse=True)
def fresh_default_backend():
    RedisCacheBackend.shared.cache_clear()
    yield
    RedisCacheBackend.shared.cache_clear()


def test_redis_url_set_after_import_is_used_on_first_cache_call(monkeypatch):
    monkeypatch.setenv("LIGHTAPI_REDIS_URL", LATE_URL)

    with patch("lightapi.cache.redis.from_url") as from_url:
        from_url.return_value.get.return_value = None
        RedisCacheBackend.shared().get("any-key")

    assert from_url.call_args.args[0] == LATE_URL


def test_cache_calls_share_one_client(monkeypatch):
    monkeypatch.setenv("LIGHTAPI_REDIS_URL", LATE_URL)

    with patch("lightapi.cache.redis.from_url") as from_url:
        from_url.return_value.get.return_value = None
        RedisCacheBackend.shared().get("first")
        RedisCacheBackend.shared().set("second", {"n": 1}, 30)
        cache.invalidate_cache_prefix("third")

    assert from_url.call_count == 1
