"""Row persistence for one mapped endpoint class."""

from __future__ import annotations

import datetime
from typing import Any, Protocol

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, class_mapper

FIRST_VERSION = 1

# SQLite (and every backend LightAPI supports) stores an id in a signed
# 64-bit column; a pk outside this range can never match a row, so treat it
# as not-found instead of letting the driver raise OverflowError.
_MIN_PK = -(2**63)
_MAX_PK = 2**63 - 1


def _in_pk_range(pk: int) -> bool:
    return _MIN_PK <= pk <= _MAX_PK


class RowNotFound(Exception):
    """No row has the requested primary key."""


class VersionConflict(Exception):
    """The row exists, but at a different ``version`` than the caller sent."""


class VersionedRow(Protocol):
    """What every LightAPI table has: a primary key and a version counter."""

    id: Any
    version: Any

    def __init__(self, **columns: Any) -> None: ...


class Repository:
    """Reads and writes rows through an open Session.

    Owns the two storage rules of a LightAPI table: the ``created_at`` /
    ``updated_at`` timestamps and optimistic locking on ``version``.
    """

    def __init__(self, model: type[VersionedRow], session: Session) -> None:
        self._model = model
        self._session = session

    @property
    def nullable_columns(self) -> set[str]:
        return {
            attr.key
            for attr in class_mapper(self._model).column_attrs
            if any(column.nullable for column in attr.columns)
        }

    def get(self, pk: int) -> Any:
        if not _in_pk_range(pk):
            raise RowNotFound(pk)
        model = self._model
        row = (
            self._session.execute(select(model).where(model.id == pk)).scalars().first()
        )
        if row is None:
            raise RowNotFound(pk)
        return row

    def add(self, values: dict[str, Any]) -> Any:
        now = _utcnow()
        row = self._model(
            **values, created_at=now, updated_at=now, version=FIRST_VERSION
        )
        self._session.add(row)
        self._session.flush()  # executes INSERT, populates auto-increment id
        self._session.refresh(row)  # re-loads DB-generated columns
        return row

    def update(self, pk: int, expected_version: int, values: dict[str, Any]) -> Any:
        """Write ``values`` only if the row is still at ``expected_version``."""
        if not _in_pk_range(pk):
            raise RowNotFound(pk)
        model = self._model
        result = self._session.execute(
            update(model)
            .where(model.id == pk, model.version == expected_version)
            .values(**values, version=expected_version + 1, updated_at=_utcnow())
        )
        if result.rowcount == 0:
            exists = self._session.execute(
                select(model.id).where(model.id == pk)
            ).first()
            self._session.rollback()
            raise VersionConflict(pk) if exists else RowNotFound(pk)
        # Re-fetch so every column, updated_at and version included, is current.
        return self.get(pk)

    def delete(self, pk: int) -> None:
        if not _in_pk_range(pk):
            raise RowNotFound(pk)
        model = self._model
        deleted = self._session.execute(
            delete(model).where(model.id == pk).returning(model.id)
        ).first()
        if deleted is None:
            raise RowNotFound(pk)


def _utcnow() -> datetime.datetime:
    """Naive UTC, which is what the DateTime columns store."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
