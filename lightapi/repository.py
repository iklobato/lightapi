"""Row persistence for one mapped endpoint class."""

from __future__ import annotations

import datetime
import logging
from typing import Any, Final, Protocol

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, class_mapper

from lightapi.constants import INT64_MAX, INT64_MIN

FIRST_VERSION: Final = 1
logger = logging.getLogger(__name__)


class RowNotFound(Exception):
    """No row has the requested primary key."""


class VersionConflict(Exception):
    """The row exists, but at a different ``version`` than the caller sent."""


class ConstraintViolation(Exception):
    """The database refused the write: a unique, foreign-key or check constraint."""


class VersionedRow(Protocol):
    """What every LightAPI table has: a primary key and a version counter."""

    id: Any
    version: Any

    def __init__(self, **columns: Any) -> None: ...  # noqa: ANN401  column values


class Repository:
    """Reads and writes rows through an open Session.

    Owns the two storage rules of a LightAPI table: the ``created_at`` /
    ``updated_at`` timestamps and optimistic locking on ``version``.
    """

    # SQLite (and every backend LightAPI supports) stores an id in a signed
    # 64-bit column; a pk outside this range can never match a row, so treat it
    # as not-found instead of letting the driver raise OverflowError.
    _MIN_PK: Final = INT64_MIN
    _MAX_PK: Final = INT64_MAX

    def __init__(self, model: type[VersionedRow], session: Session) -> None:
        self._model = model
        self._session = session

    @classmethod
    def _in_pk_range(cls, pk: int) -> bool:
        return cls._MIN_PK <= pk <= cls._MAX_PK

    @staticmethod
    def utcnow() -> datetime.datetime:
        """Naive UTC, which is what the DateTime columns store and default to."""
        return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    @property
    def nullable_columns(self) -> set[str]:
        # class_mapper() and column_attrs are memoised by SQLAlchemy; caching the
        # result per class here (functools.cache) pinned every endpoint class and
        # its engine for the life of the process.
        return {
            attr.key
            for attr in class_mapper(self._model).column_attrs
            if any(column.nullable for column in attr.columns)
        }

    def get(self, pk: int) -> VersionedRow:
        if not self._in_pk_range(pk):
            raise RowNotFound(pk)
        model = self._model
        row = (
            self._session.execute(select(model).where(model.id == pk)).scalars().first()
        )
        if row is None:
            raise RowNotFound(pk)
        return row

    def add(self, values: dict[str, Any]) -> VersionedRow:
        now = self.utcnow()
        row = self._model(
            **values, created_at=now, updated_at=now, version=FIRST_VERSION
        )
        self._session.add(row)
        try:
            self._session.flush()  # executes INSERT, populates auto-increment id
        except IntegrityError as exc:
            raise self._refused(exc) from exc
        self._session.refresh(row)  # re-loads DB-generated columns
        return row

    def _refused(self, exc: IntegrityError) -> ConstraintViolation:
        """Roll back and turn the database's refusal into a ConstraintViolation.

        Logged with the table and the driver's text: a unique clash is a client
        conflict, but a NOT NULL or CHECK failure usually means the schema and the
        table disagree, and the operator should see that even though the client
        only gets a 409.
        """
        self._session.rollback()
        logger.info(
            "Constraint violation on %s: %s",
            class_mapper(self._model).local_table,
            exc.orig,
        )
        return ConstraintViolation(str(exc.orig))

    def update(
        self, pk: int, expected_version: int, values: dict[str, Any]
    ) -> VersionedRow:
        """Write ``values`` only if the row is still at ``expected_version``."""
        if not self._in_pk_range(pk):
            raise RowNotFound(pk)
        model = self._model
        try:
            result = self._session.execute(
                update(model)
                .where(model.id == pk, model.version == expected_version)
                .values(
                    **values, version=expected_version + 1, updated_at=self.utcnow()
                )
            )
        except IntegrityError as exc:
            raise self._refused(exc) from exc
        if result.rowcount == 0:
            exists = self._session.execute(
                select(model.id).where(model.id == pk)
            ).first()
            self._session.rollback()
            raise VersionConflict(pk) if exists else RowNotFound(pk)
        # Re-fetch so every column, updated_at and version included, is current.
        return self.get(pk)

    def delete(self, pk: int) -> None:
        if not self._in_pk_range(pk):
            raise RowNotFound(pk)
        model = self._model
        try:
            deleted = self._session.execute(
                delete(model).where(model.id == pk).returning(model.id)
            ).first()
        except IntegrityError as exc:
            raise self._refused(exc) from exc
        if deleted is None:
            raise RowNotFound(pk)
