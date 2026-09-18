"""Session context managers for sync and async SQLAlchemy usage."""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, Generator, TypeVar

from sqlalchemy.orm import Session
from sqlalchemy.pool import SingletonThreadPool, StaticPool
from starlette.concurrency import run_in_threadpool

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

T = TypeVar("T")

# In-memory SQLite runs on one of these. SingletonThreadPool gives every thread
# its own empty database, and StaticPool shares a single connection that is not
# safe to use from two threads at once.
_SINGLE_CONNECTION_POOLS = (SingletonThreadPool, StaticPool)


@contextmanager
def get_sync_session(engine: Engine) -> Generator[Session, None, None]:
    """Yield a sync Session; commit on exit, rollback and re-raise on exception."""
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


@asynccontextmanager
async def get_async_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield AsyncSession (expire_on_commit=False); commit on exit, rollback on exception."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def run_blocking(engine: Engine, fn: Callable[..., T], *args: Any) -> T:
    """Run a blocking database call in a worker thread so the event loop stays free.

    Engines on a single-connection pool run the call in place instead.
    """
    if isinstance(engine.pool, _SINGLE_CONNECTION_POOLS):
        return fn(*args)
    return await run_in_threadpool(fn, *args)
