"""Repository owns optimistic locking; patch_schema is built once per endpoint."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from lightapi import LightApi, RestEndpoint, get_sync_session
from lightapi.fields import Field as LField
from lightapi.repository import Repository, RowNotFound, VersionConflict
from lightapi.schema import patch_schema

MISSING_PK = 9999


class LedgerEntry(RestEndpoint):
    memo: str = LField(min_length=1)


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine)
    app.register({"/ledgerentries": LedgerEntry})
    app.build_app()
    return engine


def _added_pk(engine) -> int:
    with get_sync_session(engine) as session:
        return Repository(LedgerEntry, session).add({"memo": "opening"}).id


def test_update_at_current_version_writes_and_bumps_version(engine):
    pk = _added_pk(engine)

    with get_sync_session(engine) as session:
        row = Repository(LedgerEntry, session).update(pk, 1, {"memo": "changed"})

        assert row.memo == "changed"
        assert row.version == 2


def test_update_at_stale_version_raises_conflict_and_keeps_the_row(engine):
    pk = _added_pk(engine)

    with get_sync_session(engine) as session:
        repository = Repository(LedgerEntry, session)
        with pytest.raises(VersionConflict):
            repository.update(pk, 7, {"memo": "lost update"})

        assert repository.get(pk).memo == "opening"


def test_update_of_missing_row_raises_not_found(engine):
    with get_sync_session(engine) as session:
        with pytest.raises(RowNotFound):
            Repository(LedgerEntry, session).update(MISSING_PK, 1, {"memo": "x"})


def test_delete_of_missing_row_raises_not_found(engine):
    with get_sync_session(engine) as session:
        with pytest.raises(RowNotFound):
            Repository(LedgerEntry, session).delete(MISSING_PK)


@pytest.mark.parametrize("pk", [2**63, -(2**63) - 1, 10**30])
def test_get_of_a_pk_outside_sqlite_int64_range_raises_not_found(engine, pk):
    """A pk this large can never match a row; used to raise OverflowError."""
    with get_sync_session(engine) as session:
        with pytest.raises(RowNotFound):
            Repository(LedgerEntry, session).get(pk)


def test_update_of_a_pk_outside_sqlite_int64_range_raises_not_found(engine):
    with get_sync_session(engine) as session:
        with pytest.raises(RowNotFound):
            Repository(LedgerEntry, session).update(2**63, 1, {"memo": "x"})


def test_delete_of_a_pk_outside_sqlite_int64_range_raises_not_found(engine):
    with get_sync_session(engine) as session:
        with pytest.raises(RowNotFound):
            Repository(LedgerEntry, session).delete(2**63)


def test_patch_schema_is_built_once_per_create_schema():
    first = patch_schema(LedgerEntry.__schema_create__)
    second = patch_schema(LedgerEntry.__schema_create__)

    assert first is second
    assert first.model_validate({}).model_dump(exclude_unset=True) == {}
