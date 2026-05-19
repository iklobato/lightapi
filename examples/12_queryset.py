"""LightAPI Example 12 - Custom Queryset.

Demonstrates:
- queryset() method override
- Dynamic filtering based on request parameters
- Programmatic query modification

Notes:
    Uses SQLite by default (swap DATABASE_URL for PostgreSQL).

Run with:
    python examples/12_queryset.py

Then try:
    # Get all books
    curl http://localhost:8000/books

    # Get only published books
    curl "http://localhost:8000/books?published_only=true"

    # Get only expensive books (> $50)
    curl "http://localhost:8000/books?min_price=50"
"""

from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

from lightapi import HttpMethod, LightApi, RestEndpoint
from lightapi.fields import Field

DATABASE_URL = "sqlite:///:memory:"


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Endpoint with custom queryset filtering."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    price: float = Field(ge=0.0)
    published: bool = Field(default=True)

    def queryset(self, request):
        """Custom queryset with dynamic filtering."""
        cls = type(self)
        qs = select(cls._model_class)

        # Filter by published_only
        if request.query_params.get("published_only") == "true":
            qs = qs.where(cls._model_class.published.is_(True))

        # Filter by minimum price
        min_price = request.query_params.get("min_price")
        if min_price:
            try:
                qs = qs.where(cls._model_class.price >= float(min_price))
            except ValueError:
                pass

        return qs


if __name__ == "__main__":
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine)
    app.register({"/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
