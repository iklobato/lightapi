"""The process-wide Redis client is created on first use, not at import time."""

from unittest.mock import patch

import pytest

from lightapi import cache

LATE_URL = "redis://configured-after-import:6379/3"


@pytest.fixture(autouse=True)
def fresh_default_backend():
    cache._default_backend.cache_clear()
    yield
    cache._default_backend.cache_clear()


def test_redis_url_set_after_import_is_used_on_first_cache_call(monkeypatch):
    monkeypatch.setenv("LIGHTAPI_REDIS_URL", LATE_URL)

    with patch("lightapi.cache.redis.from_url") as from_url:
        cache.get_cached("any-key")

    assert from_url.call_args.args[0] == LATE_URL


def test_cache_calls_share_one_client(monkeypatch):
    monkeypatch.setenv("LIGHTAPI_REDIS_URL", LATE_URL)

    with patch("lightapi.cache.redis.from_url") as from_url:
        cache.get_cached("first")
        cache.set_cached("second", {"n": 1}, 30)
        cache.invalidate_cache_prefix("third")

    assert from_url.call_count == 1
