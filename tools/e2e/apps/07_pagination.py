"""e2e app for scenario 07: page-number and cursor pagination."""

import os

from sqlalchemy import create_engine

from lightapi import Field, LightApi, Pagination, RestEndpoint


class PageItem(RestEndpoint):
    label: str = Field(min_length=1)

    class Meta:
        table = "e2e07_page_items"
        pagination = Pagination(page_size=2)


class CursorItem(RestEndpoint):
    label: str = Field(min_length=1)

    class Meta:
        table = "e2e07_cursor_items"
        pagination = Pagination(style="cursor", page_size=2)


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/pages": PageItem, "/cursor": CursorItem})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
