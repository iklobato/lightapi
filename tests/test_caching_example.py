import time
from unittest.mock import MagicMock, patch

import pytest

from examples.caching_example import (
    ConfigurableCacheEndpoint,
    CustomCache,
    WeatherEndpoint,
)


class TestCustomCache:
    """Test suite for the CustomCache class from caching_example.py.

    This class tests the in-memory cache implementation, including key
    management, TTL handling, and cache operations.
    """

    @pytest.fixture
    def cache(self):
        """Create a CustomCache instance for testing.

        Returns:
            CustomCache: A fresh instance of the CustomCache class.
        """
        return CustomCache()

    @patch("examples.caching_example.print")
    def test_set_and_get(self, mock_print, cache):
        """Test that set stores a value and get retrieves it.

        Args:
            mock_print: Mock for print to capture logging.
            cache: The cache fixture.
        """
        # Set a value in the cache
        cache.set("test_key", "test_value")

        # Verify the value was stored with prefix
        cache_key = "custom_cache:test_key"
        assert cache_key in cache.cache_data
        assert cache.cache_data[cache_key]["value"] == "test_value"

        # Get the value from the cache
        value = cache.get("test_key")

        # Verify the value is retrieved correctly
        assert value == "test_value"

        # Verify logging messages
        mock_print.assert_any_call("Cache SET for 'test_key' (expires in 60s)")
        mock_print.assert_any_call("Cache HIT for 'test_key'")

    @patch("examples.caching_example.time.time")
    @patch("examples.caching_example.print")
    def test_ttl_expiration(self, mock_print, mock_time, cache):
        """Test that cached values expire after their TTL.

        Args:
            mock_print: Mock for print to capture logging.
            mock_time: Mock for time.time to control timing.
            cache: The cache fixture.
        """
        # Set up timing sequence
        current_time = 1000.0
        mock_time.side_effect = [current_time, current_time + 30, current_time + 61]

        # Set a value in the cache
        cache.set("test_key", "test_value")

        # Get it before expiration
        value1 = cache.get("test_key")
        assert value1 == "test_value"
        mock_print.assert_any_call("Cache HIT for 'test_key'")

        # Get it after expiration
        value2 = cache.get("test_key")
        assert value2 is None
        mock_print.assert_any_call("Cache MISS for 'test_key'")

        # Verify expired entry was removed
        cache_key = "custom_cache:test_key"
        assert cache_key not in cache.cache_data

    @patch("examples.caching_example.print")
    def test_custom_ttl(self, mock_print, cache):
        """Test that set accepts a custom TTL value.

        Args:
            mock_print: Mock for print to capture logging.
            cache: The cache fixture.
        """
        # Set a value with a custom TTL
        custom_ttl = 120
        cache.set("test_key", "test_value", custom_ttl)

        # Verify the TTL was stored correctly
        cache_key = "custom_cache:test_key"
        expiration = cache.cache_data[cache_key]["expires_at"]
        assert expiration > time.time() + 119  # just under 120 seconds

        # Verify logging message shows custom TTL
        mock_print.assert_any_call(
            f"Cache SET for 'test_key' (expires in {custom_ttl}s)"
        )

    @patch("examples.caching_example.print")
    def test_delete(self, mock_print, cache):
        """Test that delete removes a key from the cache.

        Args:
            mock_print: Mock for print to capture logging.
            cache: The cache fixture.
        """
        # Set some values
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Delete one key
        cache.delete("key1")

        # Verify the key was removed
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

        # Verify logging message
        mock_print.assert_any_call("Cache DELETE for 'key1'")

    @patch("examples.caching_example.print")
    def test_flush(self, mock_print, cache):
        """Test that flush clears all keys from the cache.

        Args:
            mock_print: Mock for print to capture logging.
            cache: The cache fixture.
        """
        # Set some values
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Flush the cache
        cache.flush()

        # Verify all keys were removed
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert not cache.cache_data

        # Verify logging message
        mock_print.assert_any_call("Cache FLUSH")


class TestWeatherEndpoint:
    """Test suite for the WeatherEndpoint class from caching_example.py.

    This class tests the caching behavior of the WeatherEndpoint, including
    cache hits, misses, and cache invalidation.
    """

    @pytest.fixture
    def endpoint(self):
        """Create a WeatherEndpoint instance with a cache for testing.

        Returns:
            WeatherEndpoint: A configured endpoint instance.
        """
        endpoint = WeatherEndpoint()
        endpoint.cache = CustomCache()
        return endpoint

    @patch("examples.caching_example.time.sleep")
    @patch("examples.caching_example.print")
    def test_get_cache_miss(self, mock_print, mock_sleep, endpoint):
        """Test that get generates new data on cache miss.

        Args:
            mock_print: Mock for print to capture logging.
            mock_sleep: Mock for time.sleep to prevent actual delays.
            endpoint: The endpoint fixture.
        """

        # Create a mock request
        class MockRequest:
            query_params = {"city": "London"}

        # Call the get method (first call, should be a cache miss)
        response = endpoint.get(MockRequest())

        # Verify the response
        assert response.headers["X-Cache"] == "MISS"
        assert response.body["city"] == "London"
        assert "temperature" in response.body
        assert "condition" in response.body

        # Verify the cache was checked and set
        mock_print.assert_any_call("Cache MISS for 'weather:London'")
        mock_print.assert_any_call("Fetching weather data for London...")
        mock_print.assert_any_call("Cache SET for 'weather:London' (expires in 30s)")

        # Verify sleep was called to simulate slow operation
        mock_sleep.assert_called_once_with(0.1)

    @patch("examples.caching_example.time.sleep")
    @patch("examples.caching_example.print")
    def test_get_cache_hit(self, mock_print, mock_sleep, endpoint):
        """Test that get returns cached data on cache hit.

        Args:
            mock_print: Mock for print to capture logging.
            mock_sleep: Mock for time.sleep to prevent actual delays.
            endpoint: The endpoint fixture.
        """

        # Create a mock request
        class MockRequest:
            query_params = {"city": "London"}

        # Preset the cache with data
        cached_data = {
            "city": "London",
            "temperature": 20,
            "condition": "Sunny",
            "humidity": 50,
            "wind_speed": 10,
            "timestamp": time.time(),
        }
        endpoint.cache.set("weather:London", cached_data)

        # Reset the mocks to clear preset calls
        mock_print.reset_mock()
        mock_sleep.reset_mock()

        # Call the get method (should be a cache hit)
        response = endpoint.get(MockRequest())

        # Verify the response
        assert response.headers["X-Cache"] == "HIT"
        assert response.body == cached_data

        # Verify the cache was checked but not set
        mock_print.assert_any_call("Cache HIT for 'weather:London'")

        # Verify sleep was not called (no slow operation)
        mock_sleep.assert_not_called()

    @patch("examples.caching_example.print")
    def test_delete_specific_city(self, mock_print, endpoint):
        """Test that delete removes cache for a specific city.

        Args:
            mock_print: Mock for print to capture logging.
            endpoint: The endpoint fixture.
        """
        # Preset the cache with data for multiple cities
        endpoint.cache.set("weather:London", {"city": "London", "temperature": 20})
        endpoint.cache.set("weather:Paris", {"city": "Paris", "temperature": 25})

        # Create a mock request for deleting London
        class MockRequest:
            query_params = {"city": "London"}

        # Call the delete method
        response, status_code = endpoint.delete(MockRequest())

        # Verify the response
        assert status_code == 200
        assert response["message"] == "Cache for London cleared"

        # Verify London was deleted but Paris remains
        assert endpoint.cache.get("weather:London") is None
        assert endpoint.cache.get("weather:Paris") is not None

        # Verify delete cache method was called
        mock_print.assert_any_call("Cache DELETE for 'weather:London'")

    @patch("examples.caching_example.print")
    def test_delete_all_cities(self, mock_print, endpoint):
        """Test that delete with no city param clears all cache.

        Args:
            mock_print: Mock for print to capture logging.
            endpoint: The endpoint fixture.
        """
        # Preset the cache with data for multiple cities
        endpoint.cache.set("weather:London", {"city": "London", "temperature": 20})
        endpoint.cache.set("weather:Paris", {"city": "Paris", "temperature": 25})

        # Create a mock request without city param
        class MockRequest:
            query_params = {}

        # Call the delete method
        response, status_code = endpoint.delete(MockRequest())

        # Verify the response
        assert status_code == 200
        assert response["message"] == "All weather cache cleared"

        # Verify all cities were deleted
        assert endpoint.cache.get("weather:London") is None
        assert endpoint.cache.get("weather:Paris") is None

        # Verify flush cache method was called
        mock_print.assert_any_call("Cache FLUSH")


class TestConfigurableCacheEndpoint:
    """Test suite for the ConfigurableCacheEndpoint class from caching_example.py.

    This class tests the configurable caching behavior, including custom TTL settings.
    """

    @pytest.fixture
    def endpoint(self):
        """Create a ConfigurableCacheEndpoint instance for testing.

        Returns:
            ConfigurableCacheEndpoint: A configured endpoint instance.
        """
        endpoint = ConfigurableCacheEndpoint()
        endpoint.cache = CustomCache()
        return endpoint

    @patch("examples.caching_example.time.sleep")
    @patch("examples.caching_example.print")
    def test_get_with_custom_ttl(self, mock_print, mock_sleep, endpoint):
        """Test that get respects custom TTL from query params.

        Args:
            mock_print: Mock for print to capture logging.
            mock_sleep: Mock for time.sleep to prevent actual delays.
            endpoint: The endpoint fixture.
        """

        # Create a mock request with custom TTL
        class MockRequest:
            query_params = {"id": "resource123", "ttl": "45"}  # 45 seconds TTL

        # Call the get method
        response = endpoint.get(MockRequest())

        # Verify the response
        assert response.headers["X-Cache"] == "MISS"
        assert response.body["id"] == "resource123"
        assert "value" in response.body
        assert "generated_at" in response.body

        # Verify cache was set with custom TTL
        mock_print.assert_any_call(
            "Cache SET for 'resource:resource123' (expires in 45s)"
        )

        # Verify sleep was called to simulate slow operation
        mock_sleep.assert_called_once_with(1)

    @patch("examples.caching_example.time.sleep")
    @patch("examples.caching_example.print")
    def test_get_with_default_ttl(self, mock_print, mock_sleep, endpoint):
        """Test that get uses default TTL when not specified.

        Args:
            mock_print: Mock for print to capture logging.
            mock_sleep: Mock for time.sleep to prevent actual delays.
            endpoint: The endpoint fixture.
        """

        # Create a mock request without TTL
        class MockRequest:
            query_params = {
                "id": "resource123",
            }

        # Call the get method
        response = endpoint.get(MockRequest())

        # Verify the response
        assert response.headers["X-Cache"] == "MISS"

        # Verify cache was set with default TTL
        mock_print.assert_any_call(
            "Cache SET for 'resource:resource123' (expires in 60s)"
        )

    @patch("examples.caching_example.time.sleep")
    @patch("examples.caching_example.print")
    def test_get_cache_hit(self, mock_print, mock_sleep, endpoint):
        """Test that get uses cached data when available.

        Args:
            mock_print: Mock for print to capture logging.
            mock_sleep: Mock for time.sleep to prevent actual delays.
            endpoint: The endpoint fixture.
        """

        # Create a mock request
        class MockRequest:
            query_params = {
                "id": "resource123",
            }

        # Preset the cache with data
        cached_data = {"id": "resource123", "value": 42, "generated_at": time.time()}
        endpoint.cache.set("resource:resource123", cached_data)

        # Reset the mocks to clear preset calls
        mock_print.reset_mock()
        mock_sleep.reset_mock()

        # Call the get method
        response = endpoint.get(MockRequest())

        # Verify the response
        assert response.headers["X-Cache"] == "HIT"
        assert response.body == cached_data

        # Verify sleep was not called (no slow operation)
        mock_sleep.assert_not_called()
