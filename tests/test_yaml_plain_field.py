"""Declarative YAML fields without constraints must still persist.

Regression: a field like ``price: {type: float}`` (no constraints, no default)
used to get an Ellipsis class attribute that blocked SQLAlchemy from mapping the
column, so its value was silently dropped on INSERT.
"""

import textwrap

from starlette.testclient import TestClient

from lightapi import LightApi


def test_constraintless_field_is_persisted(tmp_path) -> None:
    config = tmp_path / "lightapi.yaml"
    config.write_text(textwrap.dedent(f"""
            database:
              url: "sqlite:///{tmp_path / 'plain.db'}"
            endpoints:
              - route: /products
                fields:
                  name: {{ type: str, max_length: 200 }}
                  price: {{ type: float }}
                meta:
                  methods: [GET, POST]
                  authentication: {{ permission: AllowAny }}
            """))

    app = LightApi.from_config(str(config))
    client = TestClient(app.build_app())

    resp = client.post("/products", json={"name": "Widget", "price": 9.5})
    assert resp.status_code == 201
    assert resp.json()["price"] == 9.5

    listing = client.get("/products").json()["results"]
    assert listing[0]["price"] == 9.5
