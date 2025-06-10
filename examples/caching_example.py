import random
import time

from sqlalchemy import Column, Integer, String

from lightapi.cache import RedisCache
from lightapi.core import LightApi, Response
from lightapi.rest import RestEndpoint


# Custom cache implementation
class CustomCache(RedisCache):
    # Cache prefix to avoid key collisions
    prefix = "custom_cache:"

    # Default cache expiration time (in seconds)
    expiration = 60  # 1 minute

    # Simulate Redis functionality for demonstration
    # In a real application, you would connect to a Redis server
    def __init__(self):
        self.cache_data = {}

    def get(self, key):
        cache_key = f"{self.prefix}{key}"

        # Check if key exists and is not expired
        if cache_key in self.cache_data:
            entry = self.cache_data[cache_key]
            # Check if entry is expired
            if entry["expires_at"] > time.time():
                print(f"Cache HIT for '{key}'")
                return entry["value"]
            else:
                # Remove expired entry
                del self.cache_data[cache_key]

        print(f"Cache MISS for '{key}'")
        return None

    def set(self, key, value, expiration=None):
        cache_key = f"{self.prefix}{key}"
        expires_at = time.time() + (expiration or self.expiration)

        self.cache_data[cache_key] = {"value": value, "expires_at": expires_at}
        print(f"Cache SET for '{key}' (expires in {expiration or self.expiration}s)")

    def delete(self, key):
        cache_key = f"{self.prefix}{key}"
        if cache_key in self.cache_data:
            del self.cache_data[cache_key]
            print(f"Cache DELETE for '{key}'")

    def flush(self):
        self.cache_data = {}
        print("Cache FLUSH")


# Endpoint with slow operation that benefits from caching
class WeatherEndpoint(RestEndpoint):
    __abstract__ = True  # Not a database model

    class Configuration:
        caching_class = CustomCache
        caching_method_names = ["GET"]  # Only cache GET requests

    def get(self, request):
        # Get the city from path parameters or query parameters or use default
        city = None

        # Check path_params if available
        if hasattr(request, "path_params"):
            city = request.path_params.get("city")

        # If city is not found in path_params, check query_params
        if not city and hasattr(request, "query_params"):
            city = request.query_params.get("city")

        # Use default if city is still not found
        if not city:
            city = "default"

        # Check if response is in cache
        cache_key = f"weather:{city}"
        cached_data = self.cache.get(cache_key)

        if cached_data:
            # Add header to indicate cache hit
            return Response(cached_data, headers={"X-Cache": "HIT"})

        # Simulate a slow API call (3 seconds)
        print(f"Fetching weather data for {city}...")
        time.sleep(0.1)  # Reduced for tests

        # Generate random weather data
        data = {
            "city": city,
            "temperature": random.randint(-10, 40),
            "condition": random.choice(["Sunny", "Cloudy", "Rainy", "Snowy"]),
            "humidity": random.randint(0, 100),
            "wind_speed": random.randint(0, 50),
            "timestamp": time.time(),
        }

        # Cache the response for 30 seconds
        self.cache.set(cache_key, data, 30)

        # Return the response with cache miss header
        return Response(data, headers={"X-Cache": "MISS"})

    def delete(self, request):
        # Clear weather cache for a specific city or all cities
        city = request.query_params.get("city")

        if city:
            self.cache.delete(f"weather:{city}")
            return {"message": f"Cache for {city} cleared"}, 200
        else:
            self.cache.flush()
            return {"message": "All weather cache cleared"}, 200


# Configurable endpoint with different cache behaviors
class ConfigurableCacheEndpoint(RestEndpoint):
    __abstract__ = True  # Not a database model

    class Configuration:
        caching_class = CustomCache
        caching_method_names = ["GET"]

    def get(self, request):
        # Get configuration from query parameters
        cache_ttl = request.query_params.get("ttl")
        resource_id = request.query_params.get("id", "default")

        # Create a unique cache key
        cache_key = f"resource:{resource_id}"

        # Check cache
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return Response(cached_data, headers={"X-Cache": "HIT"})

        # Simulate slow operation
        time.sleep(1)

        # Generate some data
        data = {
            "id": resource_id,
            "value": random.randint(1, 1000),
            "generated_at": time.time(),
        }

        # Cache with custom TTL if provided
        if cache_ttl and cache_ttl.isdigit():
            self.cache.set(cache_key, data, int(cache_ttl))
        else:
            self.cache.set(cache_key, data)  # Use default TTL

        return Response(data, headers={"X-Cache": "MISS"})


if __name__ == "__main__":
    app = LightApi(
        database_url="sqlite:///caching_example.db",
        swagger_title="Caching Example",
        swagger_version="1.0.0",
        swagger_description="Example showing caching capabilities with LightAPI",
    )

    app.register(
        {"/weather/{city}": WeatherEndpoint, "/resource": ConfigurableCacheEndpoint}
    )

    print("Server running at http://localhost:8000")
    print("API documentation available at http://localhost:8000/docs")
    print("\nTry these examples to see caching in action:")
    print("1. Get weather (first request is slow, subsequent requests use cache):")
    print("   curl http://localhost:8000/weather/London")
    print("2. Try a different city:")
    print("   curl http://localhost:8000/weather/Tokyo")
    print("3. Clear cache for a specific city:")
    print("   curl -X DELETE http://localhost:8000/weather/London")
    print("4. Clear all weather cache:")
    print("   curl -X DELETE http://localhost:8000/weather")
    print("5. Try a resource with custom cache TTL (in seconds):")
    print("   curl http://localhost:8000/resource?id=123&ttl=10")

    app.run(host="localhost", port=8000, debug=True)
