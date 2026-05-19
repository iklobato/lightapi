"""LightAPI Example 08 - Filtering & Search.

Demonstrates:
- FieldFilter: Filter by exact field values (?genre=fiction)
- SearchFilter: Full-text search (?search=term)
- OrderingFilter: Sort results (?ordering=price or ?ordering=-price)
- Combining filters

Notes:
    Uses SQLite by default (swap DATABASE_URL for PostgreSQL).

Run with:
    python examples/08_filtering.py

Then try:
    # Filter by field
    curl "http://localhost:8000/books?genre=Fiction"

    # Search (searches title and author)
    curl "http://localhost:8000/books?search=clean"

    # Order by price ascending
    curl "http://localhost:8000/books?ordering=price"

    # Order by price descending
    curl "http://localhost:8000/books?ordering=-price"

    # Combine filters
    curl "http://localhost:8000/books?genre=Fiction&search=code&ordering=-price"
"""

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from lightapi import Filtering, HttpMethod, LightApi, RestEndpoint
from lightapi.fields import Field
from lightapi.filters import FieldFilter, OrderingFilter, SearchFilter

DATABASE_URL = "sqlite:///:memory:"


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Endpoint with filtering, search, and ordering."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    price: float = Field(ge=0.0)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["genre"],  # ?genre=fiction
            search=["title", "author"],  # ?search=term
            ordering=["title", "price"],  # ?ordering=price or -price
        )


if __name__ == "__main__":
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine)
    app.register({"/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
