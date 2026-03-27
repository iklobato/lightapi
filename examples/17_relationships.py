"""LightAPI Example 17 - Relationships & Joins.

Demonstrates:
- Foreign key fields
- Including related data via join

Prerequisites:
    PostgreSQL must be running.

Run with:
    python examples/17_relationships.py

Then try:
    curl -X POST http://localhost:8000/authors -H 'Content-Type: application/json' -d '{"name":"John Doe"}'
    curl -X POST http://localhost:8000/books -H 'Content-Type: application/json' -d '{"title":"Test Book","author_id":1}'
    curl http://localhost:8000/books
"""

from sqlalchemy import create_engine

from lightapi import HttpMethod, LightApi, RestEndpoint, Serializer
from lightapi.fields import Field


DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Endpoint with simple fields."""

    title: str = Field(min_length=1)
    author: str = Field(default="")

    class Meta:
        serializer = Serializer(
            read=["id", "title", "author"],
        )


class AuthorEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Simple author endpoint."""

    name: str = Field(min_length=1)


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    app = LightApi(engine=engine)
    app.register({"/books": BookEndpoint, "/authors": AuthorEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
