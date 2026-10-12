"""A database constraint violation is a 409, not a 500, on every write path."""

import logging

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
from lightapi.fields import Field as LField


class Account(RestEndpoint):
    email: str = LField(min_length=1, unique=True)
    name: str = LField(default="")

    class Meta:
        table = "constraint_accounts"


class AsyncAccount(RestEndpoint):
    email: str = LField(min_length=1, unique=True)

    class Meta:
        table = "constraint_async_accounts"


def _memory_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def client():
    app = LightApi(engine=_memory_engine())
    app.register({"/accounts": Account})
    with TestClient(app.build_app()) as c:
        yield c


def test_duplicate_unique_value_on_post_answers_409(client):
    assert client.post("/accounts", json={"email": "a@x"}).status_code == 201

    duplicate = client.post("/accounts", json={"email": "a@x"})

    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "constraint violation"}
    assert len(client.get("/accounts").json()["results"]) == 1


def test_update_to_duplicate_unique_value_answers_409(client):
    client.post("/accounts", json={"email": "a@x"})
    second = client.post("/accounts", json={"email": "b@x"}).json()

    collide = client.put(
        f"/accounts/{second['id']}", json={"email": "a@x", "name": "", "version": 1}
    )

    assert collide.status_code == 409
    assert collide.json() == {"detail": "constraint violation"}
    assert client.get(f"/accounts/{second['id']}").json()["email"] == "b@x"


def test_the_session_is_usable_after_the_409(client):
    client.post("/accounts", json={"email": "a@x"})
    client.post("/accounts", json={"email": "a@x"})

    assert client.post("/accounts", json={"email": "c@x"}).status_code == 201


class Shelf(RestEndpoint):
    name: str = LField(min_length=1)

    class Meta:
        table = "constraint_shelves"


class Volume(RestEndpoint):
    title: str = LField(min_length=1)
    shelf_id: int | None = LField(default=None, foreign_key="constraint_shelves.id")

    class Meta:
        table = "constraint_volumes"


def _engine_enforcing_foreign_keys():
    engine = _memory_engine()

    @event.listens_for(engine, "connect")
    def _enable(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def test_delete_of_a_referenced_row_answers_409():
    app = LightApi(engine=_engine_enforcing_foreign_keys())
    app.register({"/shelves": Shelf, "/volumes": Volume})
    with TestClient(app.build_app()) as client:
        shelf = client.post("/shelves", json={"name": "A"}).json()
        client.post("/volumes", json={"title": "t", "shelf_id": shelf["id"]})

        refused = client.delete(f"/shelves/{shelf['id']}")

        assert refused.status_code == 409
        assert refused.json() == {"detail": "constraint violation"}
        assert client.get(f"/shelves/{shelf['id']}").status_code == 200


def test_the_409_is_logged_with_the_table_name(client, caplog):
    client.post("/accounts", json={"email": "a@x"})
    with caplog.at_level(logging.INFO, logger="lightapi.repository"):
        client.post("/accounts", json={"email": "a@x"})

    messages = [record.getMessage() for record in caplog.records]
    assert any("constraint_accounts" in message for message in messages), messages


def test_duplicate_on_the_async_path_answers_409():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = LightApi(engine=engine, mode="async")
    app.register({"/asyncaccounts": AsyncAccount})
    with TestClient(app.build_app()) as client:
        assert client.post("/asyncaccounts", json={"email": "a@x"}).status_code == 201

        duplicate = client.post("/asyncaccounts", json={"email": "a@x"})

        assert duplicate.status_code == 409
        assert duplicate.json() == {"detail": "constraint violation"}
        client.portal.call(engine.dispose)
