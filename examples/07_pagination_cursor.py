"""LightAPI Example 07 - Cursor Pagination.

Demonstrates:
- Pagination with cursor style (offset-based)
- ?cursor=N query parameter
- Efficient for large datasets (doesn't count total)

Prerequisites:
    PostgreSQL must be running with default credentials.

Run with:
    python examples/07_pagination_cursor.py

Then try:
    # First request - no cursor
    curl http://localhost:8000/books
    # Returns: {"next": "cursor:base64...", "previous": null, "results": [...]}

    # Next request - use cursor from previous response
    curl "http://localhost:8000/books?cursor=<CURSOR>"

    # Response format (no count/pages):
    # {
    #   "next": "cursor:base64...",
    #   "previous": null,
    #   "results": [...]
    # }
"""

from sqlalchemy import create_engine

from lightapi import HttpMethod, LightApi, Pagination, RestEndpoint
from lightapi.fields import Field


DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Endpoint with cursor pagination."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)

    class Meta:
        pagination = Pagination(style="cursor", page_size=10)


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    app = LightApi(engine=engine)
    app.register({"/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
