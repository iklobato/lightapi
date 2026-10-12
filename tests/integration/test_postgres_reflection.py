"""T3-03: reflecting a table with a realistic mix of Postgres column types.

reflect=True does not rename the table, so this does not use
use_test_isolation (same as tests/test_reflection.py): each test creates its
own real table with a unique name instead.

Every reflected column, nullable or not, is required in the create schema
(it may be sent as null, but must be present) -- unchanged from dev, where
build_from_reflected_table also uses `...` as the pydantic default for every
column. So a JSONB/INET/ARRAY column that falls back to Any still has to be
sent (as null) on POST; the annotation being Optional[Any] does not make the
key optional.
"""

import uuid

import pytest
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, DOUBLE_PRECISION, INET, JSONB, UUID
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint

from .conftest import requires_pg_sync

pytestmark = requires_pg_sync


@pytest.fixture
def rich_table_name() -> str:
    return f"pg_reflect_probe_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def rich_table(pg_engine, rich_table_name):
    meta = MetaData()
    table = Table(
        rich_table_name,
        meta,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("label", Text, nullable=False),
        Column("code", String(20), nullable=True),
        Column("amount", Numeric(10, 2), nullable=True),
        Column("ratio", DOUBLE_PRECISION, nullable=True),
        Column("active", Boolean, nullable=True),
        Column("happened_at", DateTime, nullable=True),
        Column("day", Date, nullable=True),
        Column("moment", Time, nullable=True),
        Column("external_id", UUID, nullable=True),
        Column("payload", JSONB, nullable=True),
        Column("address", INET, nullable=True),
        Column("tags", ARRAY(String), nullable=True),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
        Column("version", BigInteger, server_default=text("1")),
    )
    meta.create_all(pg_engine)
    yield table
    with pg_engine.connect() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{rich_table_name}"'))
        conn.commit()


FULL_ROW = {
    "label": "first",
    "code": "A1",
    "amount": "12.50",
    "ratio": 0.5,
    "active": True,
    "happened_at": "2026-01-01T00:00:00",
    "day": "2026-01-01",
    "moment": "12:30:00",
    "external_id": "6f1c1f0a-5f0e-4c3b-9d2a-0c7e8f9a1b2c",
    "payload": None,
    "address": None,
    "tags": None,
}


def _client(pg_engine, rich_table_name: str, route: str) -> TestClient:
    # A distinct class per table name avoids the "same class name" mapper warning.
    meta = type("Meta", (), {"reflect": True, "table": rich_table_name})
    endpoint_cls = type(f"PgRich_{rich_table_name}", (RestEndpoint,), {"Meta": meta})

    app = LightApi(engine=pg_engine)
    app.register({route: endpoint_cls})
    return TestClient(app.build_app())


def test_known_types_are_mapped_and_validated(pg_engine, rich_table, rich_table_name):
    route = f"/{rich_table_name}"
    client = _client(pg_engine, rich_table_name, route)

    created = client.post(route, json=FULL_ROW)

    assert created.status_code == 201
    body = created.json()
    assert body["amount"] == "12.50"  # Numeric -> Decimal -> JSON string
    assert body["ratio"] == "0.5"  # DOUBLE_PRECISION is a Numeric too -> Decimal
    assert body["active"] is True
    assert body["external_id"] == FULL_ROW["external_id"]

    listed = client.get(route)
    assert listed.status_code == 200
    assert len(listed.json()["results"]) == 1


def test_unknown_types_fall_back_to_any_but_are_still_required(
    pg_engine, rich_table, rich_table_name
):
    """payload/address/tags map to Any (a WARNING is logged); the column is
    still a required key in the create schema, just nullable."""
    route = f"/{rich_table_name}"
    client = _client(pg_engine, rich_table_name, route)

    missing_unknown_column = {k: v for k, v in FULL_ROW.items() if k != "payload"}
    rejected = client.post(route, json=missing_unknown_column)
    assert rejected.status_code == 422

    accepted = client.post(route, json=FULL_ROW)
    assert accepted.status_code == 201
    assert accepted.json()["payload"] is None


def test_nullable_column_can_be_omitted_on_patch(
    pg_engine, rich_table, rich_table_name
):
    route = f"/{rich_table_name}"
    client = _client(pg_engine, rich_table_name, route)
    created = client.post(route, json=FULL_ROW).json()

    patched = client.patch(
        f"{route}/{created['id']}", json={"version": created["version"]}
    )

    assert patched.status_code == 200
    assert patched.json()["label"] == FULL_ROW["label"]
