"""Session context managers for sync and async SQLAlchemy usage."""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, AsyncGenerator, Generator

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@contextmanager
def get_sync_session(engine: Engine) -> Generator[Session, None, None]:
    """Yield a synchronous Session; commit on clean exit, rollback and re-raise on exception."""
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


@asynccontextmanager
async def get_async_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession (expire_on_commit=False); await commit on exit, rollback on exception."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
