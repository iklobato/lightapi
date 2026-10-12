"""e2e app for scenario 17: Field column options and the unique-violation path."""

import os
from decimal import Decimal

from sqlalchemy import create_engine, event

from lightapi import Field, LightApi, RestEndpoint


class Category(RestEndpoint):
    name: str = Field(min_length=1)

    class Meta:
        table = "e2e17_categories"


class Product(RestEndpoint):
    sku: str = Field(min_length=1, unique=True)
    name: str = Field(min_length=1, index=True)
    price: Decimal = Field(decimal_places=2)
    internal_note: str = Field(default="", exclude=True)
    category_id: int | None = Field(default=None, foreign_key="e2e17_categories.id")

    class Meta:
        table = "e2e17_products"


def main() -> None:
    engine = create_engine(os.environ["E2E_DB_URL"])
    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys unless each connection asks; Postgres always
        # enforces them, so both runs refuse the DELETE of a referenced category.
        @event.listens_for(engine, "connect")
        def _enforce_foreign_keys(dbapi_connection, _record) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    app = LightApi(engine=engine)
    app.register({"/categories": Category, "/products": Product})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
