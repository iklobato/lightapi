"""Reflected columns must keep validating as the types released versions used.

Clients see this: a column annotated as Decimal is a JSON string ("0.5"), one
annotated as float is a JSON number (0.5).
"""

import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Double,
    Float,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    Time,
    Uuid,
)
from sqlalchemy.dialects import postgresql, sqlite

from lightapi.schema import SchemaFactory

EXPECTED = [
    (Integer(), int),
    (BigInteger(), int),
    (SmallInteger(), int),
    (String(20), str),
    (Text(), str),
    (Boolean(), bool),
    (DateTime(), datetime.datetime),
    (Date(), datetime.date),
    (Time(), datetime.time),
    (Numeric(10, 2), Decimal),
    # Float is a Numeric in SQLAlchemy, and the released mapping tested Numeric
    # first, so every float column has always validated as Decimal.
    (Numeric(10, 2, asdecimal=False), Decimal),
    (Float(), Decimal),
    (Double(), Decimal),
    (postgresql.DOUBLE_PRECISION(), Decimal),
    (postgresql.REAL(), Decimal),
    (sqlite.REAL(), Decimal),
    (Uuid(), UUID),
    (Uuid(as_uuid=False), UUID),
    (postgresql.UUID(), UUID),
    (postgresql.UUID(as_uuid=False), UUID),
    (LargeBinary(), Any),
    (JSON(), Any),
    (postgresql.JSONB(), Any),
    (postgresql.ARRAY(Integer), Any),
    (postgresql.INET(), Any),
]


class FakeEndpoint:
    __name__ = "FakeEndpoint"


@pytest.mark.parametrize(
    ("column_type", "annotation"),
    EXPECTED,
    ids=[repr(column_type) for column_type, _ in EXPECTED],
)
def test_reflected_column_annotation(column_type, annotation):
    table = Table(
        "reflected_annotation_probe",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("value", column_type, nullable=False),
    )

    schema_create, _ = SchemaFactory.build_from_reflected_table(FakeEndpoint, table)

    assert schema_create.model_fields["value"].annotation is annotation
