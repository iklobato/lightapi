"""e2e app for scenario 17: Field column options and the unique-violation path."""

import os
from decimal import Decimal

from sqlalchemy import create_engine

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
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/categories": Category, "/products": Product})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
