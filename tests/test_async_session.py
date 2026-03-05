"""Tests for lightapi/session.py — sync and async session context managers."""
import pytest
import pytest_asyncio
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session

from lightapi.session import get_async_session, get_sync_session


class _Base(DeclarativeBase):
    pass


class _Note(_Base):
    __tablename__ = "notes_session_test"
    id = Column(Integer, primary_key=True, autoincrement=True)
    body = Column(String(200))


@pytest.fixture
def sync_engine():
    engine = create_engine("sqlite:///:memory:")
    _Base.metadata.create_all(engine)
    yield engine
    _Base.metadata.drop_all(engine)
    engine.dispose()


@pytest_asyncio.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.drop_all)
    await engine.dispose()


# ── Sync tests ────────────────────────────────────────────────────────────────


def test_get_sync_session_commits_on_exit(sync_engine):
    with get_sync_session(sync_engine) as session:
        session.add(_Note(body="hello"))

    with Session(sync_engine) as s:
        count = s.query(_Note).filter_by(body="hello").count()
    assert count == 1


def test_get_sync_session_rollback_on_exception(sync_engine):
    try:
        with get_sync_session(sync_engine) as session:
            session.add(_Note(body="should_rollback"))
            raise ValueError("forced")
    except ValueError:
        pass

    with Session(sync_engine) as s:
        count = s.query(_Note).filter_by(body="should_rollback").count()
    assert count == 0


# ── Async tests ───────────────────────────────────────────────────────────────


async def test_get_async_session_commits_on_exit(async_engine):
    async with get_async_session(async_engine) as session:
        session.add(_Note(body="async_hello"))

    async with get_async_session(async_engine) as s:
        result = await s.execute(
            text("SELECT COUNT(*) FROM notes_session_test WHERE body='async_hello'")
        )
        count = result.scalar_one()
    assert count == 1


async def test_get_async_session_rollback_on_exception(async_engine):
    try:
        async with get_async_session(async_engine) as session:
            session.add(_Note(body="async_rollback"))
            raise ValueError("forced")
    except ValueError:
        pass

    async with get_async_session(async_engine) as s:
        result = await s.execute(
            text("SELECT COUNT(*) FROM notes_session_test WHERE body='async_rollback'")
        )
        count = result.scalar_one()
    assert count == 0


async def test_get_async_session_not_shared(async_engine):
    """Two concurrent calls produce independent session objects."""
    ids: list[int] = []
    async with get_async_session(async_engine) as s1:
        ids.append(id(s1))
    async with get_async_session(async_engine) as s2:
        ids.append(id(s2))
    assert ids[0] != ids[1]


# ── Startup validation tests ──────────────────────────────────────────────────


async def test_missing_asyncio_extra_raises_config_error(monkeypatch, async_engine):
    """ConfigurationError raised when sqlalchemy[asyncio] import is unavailable."""
    import importlib
    from lightapi.exceptions import ConfigurationError
    from lightapi.lightapi import _validate_async_dependencies

    real_import = importlib.import_module

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "sqlalchemy.ext.asyncio":
            raise ImportError("mocked missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", mock_import)

    with pytest.raises(ConfigurationError, match="sqlalchemy\\[asyncio\\]"):
        _validate_async_dependencies(async_engine)


async def test_missing_dialect_driver_raises_config_error(monkeypatch, async_engine):
    """ConfigurationError with install hint when dialect driver is missing."""
    import importlib
    from lightapi.exceptions import ConfigurationError
    from lightapi.lightapi import _validate_async_dependencies

    real_import = importlib.import_module

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "aiosqlite":
            raise ImportError("mocked missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", mock_import)

    with pytest.raises(ConfigurationError, match="aiosqlite"):
        _validate_async_dependencies(async_engine)
