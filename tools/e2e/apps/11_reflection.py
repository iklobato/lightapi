"""e2e app for scenario 11: endpoints mapped onto tables that already exist."""

import os

from sqlalchemy import create_engine

from lightapi import Field, LightApi, RestEndpoint


class Product(RestEndpoint):
    class Meta:
        table = "e2e11_products"
        reflect = True


class Doc(RestEndpoint):
    notes: str = Field(default="")

    class Meta:
        table = "e2e11_docs"
        reflect = "partial"


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/products": Product, "/docs": Doc})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
