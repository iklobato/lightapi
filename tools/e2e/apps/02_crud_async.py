"""e2e app for scenario 02: the same CRUD endpoint on an async engine."""

import os

from sqlalchemy.ext.asyncio import create_async_engine

from lightapi import Field, LightApi, RestEndpoint


class Book(RestEndpoint):
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    pages: int | None = Field(default=None)

    class Meta:
        table = "e2e02_books"


def main() -> None:
    app = LightApi(engine=create_async_engine(os.environ["E2E_DB_URL"]), mode="async")
    app.register({"/books": Book})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
