"""LightAPI Example 01 - Minimal Hello World.

A minimal LightAPI application demonstrating:
- Basic RestEndpoint class
- SQLite in-memory database
- No authentication or filtering

Run with:
    python examples/01_minimal.py

Then try:
    curl http://localhost:8000/books
    curl -X POST http://localhost:8000/books \
        -H 'Content-Type: application/json' \
        -d '{"title":"Clean Code","author":"Martin"}'
    curl http://localhost:8000/books/1
    curl -X PUT http://localhost:8000/books/1 \
        -H 'Content-Type: application/json' \
        -d '{"title":"Clean Code","author":"Martin","genre":"Programming","published":true,"version":1}'
    curl -X DELETE http://localhost:8000/books/1
"""

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from lightapi import HttpMethod, LightApi, RestEndpoint
from lightapi.fields import Field


class BookEndpoint(
    RestEndpoint,
    HttpMethod.GET,
    HttpMethod.POST,
    HttpMethod.PUT,
    HttpMethod.PATCH,
    HttpMethod.DELETE,
):
    """Simple book endpoint with basic CRUD operations."""

    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1)


if __name__ == "__main__":
    # StaticPool + check_same_thread=False make :memory: usable across requests.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine)
    app.register({"/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
