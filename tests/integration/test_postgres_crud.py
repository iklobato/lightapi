"""T3-01: sync CRUD against a real Postgres engine, real connection pool."""

from decimal import Decimal
from typing import Optional

import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
from lightapi.fields import Field

from .conftest import requires_pg_sync

pytestmark = requires_pg_sync


class PgBook(RestEndpoint):
    title: str = Field(min_length=1, max_length=50)
    pages: int = Field(ge=1)
    price: Decimal = Field(decimal_places=2)
    rating: Optional[float] = Field(default=None)
    in_print: bool = Field(default=True)


@pytest.fixture
def client(pg_engine) -> TestClient:
    app = LightApi(engine=pg_engine, use_test_isolation=True)
    app.register({"/pgbooks": PgBook})
    built = TestClient(app.build_app())
    # The container is disposable per the test plan, but in practice it stays
    # up across many local runs; truncate so each test starts from zero rows
    # instead of accumulating leftovers from earlier invocations.
    with pg_engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE pgbooks RESTART IDENTITY"))
        conn.commit()
    return built


def test_create_and_list(client):
    created = client.post(
        "/pgbooks", json={"title": "Dune", "pages": 412, "price": "9.99"}
    )

    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "Dune"
    assert body["price"] == "9.99"
    assert body["version"] == 1

    listed = client.get("/pgbooks")
    assert listed.status_code == 200
    assert len(listed.json()["results"]) == 1


def test_retrieve_not_found(client):
    response = client.get("/pgbooks/9999")

    assert response.status_code == 404
    assert response.json() == {"detail": "not found"}


def test_update_with_optimistic_locking(client):
    created = client.post(
        "/pgbooks", json={"title": "Dune", "pages": 412, "price": "9.99"}
    ).json()
    pk = created["id"]

    updated = client.put(
        f"/pgbooks/{pk}",
        json={
            "title": "Dune (revised)",
            "pages": 500,
            "price": "12.99",
            "version": created["version"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    stale = client.put(
        f"/pgbooks/{pk}",
        json={"title": "x", "pages": 1, "price": "1.00", "version": 1},
    )
    assert stale.status_code == 409
    assert stale.json() == {"detail": "version conflict"}


def test_patch_partial_and_delete(client):
    created = client.post(
        "/pgbooks", json={"title": "Dune", "pages": 412, "price": "9.99"}
    ).json()
    pk = created["id"]

    patched = client.patch(
        f"/pgbooks/{pk}", json={"rating": 4.5, "version": created["version"]}
    )
    assert patched.status_code == 200
    assert patched.json()["rating"] == 4.5
    assert patched.json()["title"] == "Dune"

    deleted = client.delete(f"/pgbooks/{pk}")
    assert deleted.status_code == 204

    gone = client.get(f"/pgbooks/{pk}")
    assert gone.status_code == 404


def test_validation_error_returns_422(client):
    response = client.post("/pgbooks", json={"title": "", "pages": 0, "price": "x"})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
