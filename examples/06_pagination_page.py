"""LightAPI Example 06 - Page Number Pagination.

Demonstrates:
- Pagination with page_number style
- ?page=N query parameter
- Response includes count, pages, next, previous

Notes:
    Uses SQLite by default (swap DATABASE_URL for PostgreSQL).

Run with:
    python examples/06_pagination_page.py

Then try:
    # Create some items first
    curl -X POST http://localhost:8000/books -H 'Content-Type: application/json' -d '{"title":"Book 1","author":"Author A","price":10}'
    curl -X POST http://localhost:8000/books -H 'Content-Type: application/json' -d '{"title":"Book 2","author":"Author B","price":20}'
    # ... create more books

    # Get page 1 (default)
    curl http://localhost:8000/books

    # Get page 2
    curl http://localhost:8000/books?page=2

    # Response format:
    # {
    #   "count": 25,      // total items
    #   "pages": 3,       // total pages
    #   "next": "http://.../?page=2",
    #   "previous": null,
    #   "results": [...]
    # }
"""

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from lightapi import HttpMethod, LightApi, Pagination, RestEndpoint
from lightapi.fields import Field

DATABASE_URL = "sqlite:///:memory:"


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Endpoint with page number pagination."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    price: float = Field(ge=0.0)

    class Meta:
        pagination = Pagination(style="page_number", page_size=5)


if __name__ == "__main__":
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine)
    app.register({"/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
