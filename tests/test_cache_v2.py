"""Tests for Cache config integration (Meta.cache, FR-14a)."""

from unittest.mock import patch

import pytest
import redis
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import Cache, LightApi, RestEndpoint
from lightapi.cache import RedisCacheBackend
from lightapi.fields import Field as LField


class _RedisDown:
    """A redis client whose every call fails the way a dead server does."""

    def _fail(self, *args, **kwargs):
        raise redis.ConnectionError("Error 61 connecting to localhost:6379")

    get = setex = delete = scan_iter = ping = _fail


class CachedEndpoint(RestEndpoint):
    name: str = LField(min_length=1)

    class Meta:
        cache = Cache(ttl=60)


class CachedVaryOnEndpoint(RestEndpoint):
    label: str = LField(min_length=1)

    class Meta:
        cache = Cache(ttl=60, vary_on=["page"])


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine)
    app.register({"/cached": CachedEndpoint})
    return TestClient(app.build_app())


class TestCacheGetList:
    def test_cache_get_list_returns_cached_on_second_request(self, client):
        """First GET hits DB, second GET returns cached (when get_cached returns data)."""
        with (
            patch("lightapi.cache.RedisCacheBackend.get") as mock_get,
            patch("lightapi.cache.RedisCacheBackend.set") as mock_set,
        ):
            mock_get.return_value = None  # First call: cache miss
            resp1 = client.get("/cached")
            assert resp1.status_code == 200
            mock_set.assert_called_once()

            mock_get.return_value = {"results": [{"id": 1, "name": "cached"}]}
            mock_get.reset_mock()
            mock_set.reset_mock()
            resp2 = client.get("/cached")
            assert resp2.status_code == 200
            assert resp2.json()["results"][0]["name"] == "cached"
            mock_get.assert_called()
            mock_set.assert_not_called()


class TestCacheInvalidation:
    def test_cache_post_invalidates(self, client):
        """POST triggers cache invalidation."""
        with patch("lightapi.cache.RedisCacheBackend.invalidate_prefix") as mock_inv:
            client.post("/cached", json={"name": "new"})
            mock_inv.assert_called()

    def test_cache_put_invalidates(self, client):
        """PUT triggers cache invalidation."""
        with patch("lightapi.cache.RedisCacheBackend.invalidate_prefix") as mock_inv:
            post_resp = client.post("/cached", json={"name": "item"})
            item_id = post_resp.json()["id"]
            version = post_resp.json()["version"]
            client.put(
                f"/cached/{item_id}",
                json={"name": "updated", "version": version},
            )
            assert mock_inv.call_count >= 1

    def test_cache_delete_invalidates(self, client):
        """DELETE triggers cache invalidation."""
        with patch("lightapi.cache.RedisCacheBackend.invalidate_prefix") as mock_inv:
            post_resp = client.post("/cached", json={"name": "to_delete"})
            item_id = post_resp.json()["id"]
            client.delete(f"/cached/{item_id}")
            assert mock_inv.call_count >= 1


class TestCacheRedisUnreachable:
    def test_cache_redis_unreachable_startup_warning(self):
        """When Redis unreachable and cache configured, RuntimeWarning emitted at startup."""
        with (
            patch("lightapi.cache.RedisCacheBackend.ping", return_value=False),
            pytest.warns(RuntimeWarning, match="Redis|Cache"),
        ):
            engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            app = LightApi(engine=engine)
            app.register({"/cached": CachedEndpoint})
            app.build_app()

    def test_cache_redis_unreachable_mid_request_serves_db(self, client):
        """When the Redis client raises, GET still returns 200 from DB."""
        RedisCacheBackend.shared.cache_clear()
        try:
            with patch("lightapi.cache.redis.from_url", return_value=_RedisDown()):
                resp = client.get("/cached")
                assert resp.status_code == 200
                assert "results" in resp.json()
        finally:
            RedisCacheBackend.shared.cache_clear()


class TestCacheVaryOn:
    def test_cache_vary_on_query_params_uses_different_keys(self):
        """Cache(vary_on=["page"]) uses page param in cache key."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine)
        app.register({"/cached_vary": CachedVaryOnEndpoint})
        c = TestClient(app.build_app())
        c.post("/cached_vary", json={"label": "x"})

        with (
            patch("lightapi.cache.RedisCacheBackend.get") as mock_get,
            patch("lightapi.cache.RedisCacheBackend.set") as mock_set,
        ):
            mock_get.return_value = None
            c.get("/cached_vary?page=1")
            c.get("/cached_vary?page=2")
            keys = [c[0][0] for c in mock_set.call_args_list]
            assert len(keys) == 2
            assert keys[0] != keys[1]
