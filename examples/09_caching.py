"""LightAPI Example 09 - Redis Caching.

Demonstrates:
- Response caching with Redis
- Cache TTL (time-to-live)
- Cache invalidation on POST/PUT/DELETE
- Cache vary_on for query parameter-based caching

Prerequisites:
    PostgreSQL and Redis must be running with default credentials.
    Redis: localhost:6379

Run with:
    python examples/09_caching.py

Then try:
    # First request - cache miss, fetches from DB
    curl http://localhost:8000/books

    # Second request - cache hit, returns cached response
    # Check response header: X-Cache: HIT

    # After POST/PUT/DELETE - cache is invalidated
    curl -X POST http://localhost:8000/books \
        -H 'Content-Type: application/json' \
        -d '{"title":"New Book","author":"Author","price":10}'
"""

from sqlalchemy import create_engine

from lightapi import Cache, HttpMethod, LightApi, RestEndpoint
from lightapi.fields import Field


DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"


class BookEndpoint(
    RestEndpoint,
    HttpMethod.GET,
    HttpMethod.POST,
    HttpMethod.PUT,
    HttpMethod.PATCH,
    HttpMethod.DELETE,
):
    """Endpoint with Redis caching.

    Cache is automatically invalidated when:
    - POST creates a new record
    - PUT/PATCH updates a record
    - DELETE removes a record
    """

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    price: float = Field(ge=0.0)

    class Meta:
        # Cache responses for 30 seconds
        # vary_on=["genre"] would cache separately per genre
        cache = Cache(ttl=30)


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    app = LightApi(engine=engine)
    app.register({"/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
