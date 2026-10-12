"""e2e app for scenario 01: plain CRUD on a sync engine."""

import os

from sqlalchemy import create_engine

from lightapi import Field, LightApi, RestEndpoint


class Book(RestEndpoint):
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    pages: int | None = Field(default=None)

    class Meta:
        table = "e2e01_books"


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/books": Book})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
