"""e2e app for scenario 06: field, search and ordering filters with page pagination."""

import os

from sqlalchemy import create_engine

from lightapi import (
    Field,
    FieldFilter,
    Filtering,
    LightApi,
    OrderingFilter,
    Pagination,
    RestEndpoint,
    SearchFilter,
)


class Book(RestEndpoint):
    title: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    price: float = Field()
    pages: int = Field()
    published: bool = Field(default=True)

    class Meta:
        table = "e2e06_books"
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["genre", "published", "pages"],
            search=["title"],
            ordering=["price", "pages"],
        )
        pagination = Pagination(page_size=5)


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/books": Book})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
