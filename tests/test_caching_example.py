import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
from unittest.mock import MagicMock, patch

import pytest

from examples.caching_redis_custom import (
    ConfigurableCacheEndpoint,
    CustomCache,
    WeatherEndpoint,
)


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

    @patch("examples.caching_redis_custom.time.sleep")
    @patch("examples.caching_redis_custom.print")
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

    @patch("examples.caching_redis_custom.time.sleep")
    @patch("examples.caching_redis_custom.print")
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

    @patch("examples.caching_redis_custom.print")
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

    @patch("examples.caching_redis_custom.print")
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

    @patch("examples.caching_redis_custom.time.sleep")
    @patch("examples.caching_redis_custom.print")
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
        mock_print.assert_any_call("Cache SET for 'resource:resource123' (expires in 45s)")

        # Verify sleep was called to simulate slow operation
        mock_sleep.assert_called_once_with(1)

    @patch("examples.caching_redis_custom.time.sleep")
    @patch("examples.caching_redis_custom.print")
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
        mock_print.assert_any_call("Cache SET for 'resource:resource123' (expires in 60s)")

    @patch("examples.caching_redis_custom.time.sleep")
    @patch("examples.caching_redis_custom.print")
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
