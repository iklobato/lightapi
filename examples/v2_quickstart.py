"""LightAPI v2 — minimal quickstart example.

Run with:
    uv run python examples/v2_quickstart.py

Then try:
    curl http://localhost:8000/books
    curl -X POST http://localhost:8000/books -H 'Content-Type: application/json' -d '{"title":"Clean Code","author":"Martin"}'
    curl http://localhost:8000/books/1
"""

from sqlalchemy import create_engine

from lightapi import (
    Authentication,
    Filtering,
    HttpMethod,
    IsAdminUser,
    JWTAuthentication,
    LightApi,
    Pagination,
    RestEndpoint,
    Serializer,
)
from lightapi.fields import Field
from lightapi.filters import FieldFilter, OrderingFilter, SearchFilter


class BookEndpoint(
    RestEndpoint,
    HttpMethod.GET,
    HttpMethod.POST,
    HttpMethod.PUT,
    HttpMethod.PATCH,
    HttpMethod.DELETE,
):
    """A fully-featured book endpoint."""

    title: str = Field(min_length=1, description="Book title")
    author: str = Field(min_length=1, description="Author name")
    genre: str = Field(min_length=1, description="Genre")
    published: bool = Field(description="Is published?")

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["genre", "published"],
            search=["title", "author"],
            ordering=["title", "author"],
        )
        pagination = Pagination(style="page_number", page_size=10)
        serializer = Serializer(
            read=[
                "id",
                "title",
                "author",
                "genre",
                "published",
                "created_at",
                "version",
            ],
            write=["id", "title", "author", "genre", "published"],
        )


class AdminBookEndpoint(RestEndpoint, HttpMethod.DELETE):
    """DELETE-only endpoint protected by admin permission."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAdminUser,
        )


if __name__ == "__main__":
    engine = create_engine("sqlite:///books.db")
    app = LightApi(engine=engine)
    app.register(
        {
            "/books": BookEndpoint,
        }
    )
    app.run(host="0.0.0.0", port=8000, debug=True)
