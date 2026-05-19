"""LightAPI Example 02 - Full CRUD Operations.

Demonstrates:
- SQLite database (swap to PostgreSQL by changing DATABASE_URL)
- All 5 HTTP methods (GET, POST, PUT, PATCH, DELETE)
- Optimistic locking with version field
- Version conflict handling (409 Conflict)

Run with:
    python examples/02_crud.py

Then try:
    # Create
    curl -X POST http://localhost:8000/books \
        -H 'Content-Type: application/json' \
        -d '{"title":"Clean Code","author":"Robert C. Martin","price":49.99}'

    # Read all
    curl http://localhost:8000/books

    # Read one
    curl http://localhost:8000/books/1

    # Update (PUT requires all fields + version)
    curl -X PUT http://localhost:8000/books/1 \
        -H 'Content-Type: application/json' \
        -d '{"title":"Clean Code","author":"Robert C. Martin","price":54.99,"version":1}'

    # Partial update (PATCH)
    curl -X PATCH http://localhost:8000/books/1 \
        -H 'Content-Type: application/json' \
        -d '{"price":59.99,"version":1}'

    # Delete
    curl -X DELETE http://localhost:8000/books/1

    # Version conflict example:
    # First get version=1, then try to update with version=1 again (will fail)
"""

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from lightapi import HttpMethod, LightApi, RestEndpoint
from lightapi.fields import Field

DATABASE_URL = "sqlite:///:memory:"


class BookEndpoint(
    RestEndpoint,
    HttpMethod.GET,
    HttpMethod.POST,
    HttpMethod.PUT,
    HttpMethod.PATCH,
    HttpMethod.DELETE,
):
    """Full CRUD endpoint with optimistic locking.

    PUT and PATCH require a 'version' field. If the version doesn't match
    the database version, a 409 Conflict is returned.
    """

    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1)
    price: float = Field(ge=0.0)
    published: bool = Field(default=True)


if __name__ == "__main__":
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine)
    app.register({"/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
