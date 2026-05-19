"""LightAPI Example 17 - Relationships & Joins.

Demonstrates:
- Foreign key fields via Field(foreign_key=...)
- Two related endpoints (Author parent, Book child via author_id)

Notes:
    Uses SQLite by default (swap DATABASE_URL for PostgreSQL).
    Author rows must be created before Book rows that reference them.

Run with:
    python examples/17_relationships.py

Then try:
    curl -X POST http://localhost:8000/authors -H 'Content-Type: application/json' -d '{"name":"John Doe"}'
    curl -X POST http://localhost:8000/books -H 'Content-Type: application/json' -d '{"title":"Test Book","author_id":1}'
    curl http://localhost:8000/books
"""

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from lightapi import HttpMethod, LightApi, RestEndpoint, Serializer
from lightapi.fields import Field

DATABASE_URL = "sqlite:///:memory:"


class AuthorEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Author endpoint (parent table)."""

    name: str = Field(min_length=1)

    class Meta:
        table = "authors"


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Book endpoint with a foreign key to authors."""

    title: str = Field(min_length=1)
    author_id: int = Field(foreign_key="authors.id")

    class Meta:
        serializer = Serializer(
            read=["id", "title", "author_id"],
        )


if __name__ == "__main__":
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine)
    app.register({"/authors": AuthorEndpoint, "/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
