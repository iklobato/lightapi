"""Engine, registry and metadata holder for one LightApi app."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy import Engine, MetaData
from sqlalchemy.orm import registry
from sqlalchemy.pool import SingletonThreadPool, StaticPool
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

T = TypeVar("T")

# In-memory SQLite runs on one of these. SingletonThreadPool gives every thread
# its own empty database, and StaticPool shares a single connection that is not
# safe to use from two threads at once.
_SINGLE_CONNECTION_POOLS = (SingletonThreadPool, StaticPool)


class _ThreadState(threading.local):
    """Metadata, registry and table-name counters of one thread (test isolation).

    ``threading.local`` runs ``__init__`` again on first use from each thread.
    """

    def __init__(self) -> None:
        self.metadata = MetaData()
        self.registry = registry(metadata=self.metadata)
        self.table_counter: dict[str, int] = {}


class _GlobalState:
    """Process-wide SQLAlchemy metadata/registry, plus a thread-local copy.

    Every non-isolated SessionManager shares the one `metadata`/`registry`
    pair below. `use_test_isolation=True` gets a separate pair per thread
    instead (plus per-thread table-name counters), so tests running in
    parallel don't map two different classes onto the same table name.
    """

    def __init__(self) -> None:
        self._local = _ThreadState()
        self.reset()

    def reset(self) -> None:
        """Start over with fresh global metadata/registry.

        Lets a test that redefines an endpoint class under a name already
        used by a previous test (see tests/test_examples_e2e.py) map it
        without inheriting columns from that earlier mapping.
        """
        self.metadata = MetaData()
        self.registry = registry(metadata=self.metadata)

    @property
    def test_metadata(self) -> MetaData:
        return self._local.metadata

    @property
    def test_registry(self) -> registry:
        return self._local.registry

    def unique_table_name(self, base_name: str) -> str:
        """A table name unique to this thread, for parallel test isolation."""
        counter = self._local.table_counter.get(base_name, 0) + 1
        self._local.table_counter[base_name] = counter
        result = base_name if counter == 1 else f"{base_name}_{counter}"
        logger.debug(
            "unique_table_name: %s -> %s (counter: %s)", base_name, result, counter
        )
        return result


_state = _GlobalState()


class SessionManager:
    """Holds the engine plus the registry and metadata endpoints are mapped into.

    Sessions are opened by the CRUD code itself, not here.
    Supports both sync and async engines.
    """

    def __init__(
        self,
        engine: Any,  # noqa: ANN401  an Engine or an AsyncEngine; which is a runtime fact
        use_test_isolation: bool = False,
    ) -> None:
        """Initialize with an engine (sync or async).

        Args:
            engine: SQLAlchemy engine (sync or async)
            use_test_isolation: Whether to use test-specific registries for isolation
        """
        self._engine = engine
        self._is_async = hasattr(engine, "sync_engine")
        self._use_test_isolation = use_test_isolation

        # Use test-specific or global metadata based on configuration
        if use_test_isolation:
            self._metadata = _state.test_metadata
            self._registry = _state.test_registry
        else:
            self._metadata = _state.metadata
            self._registry = _state.registry

    @property
    def engine(self) -> Any:  # noqa: ANN401  an Engine or an AsyncEngine (see is_async)
        """Get the engine."""
        return self._engine

    @property
    def sync_engine(self) -> Engine:
        """The engine sync code can use: an AsyncEngine's underlying sync one."""
        engine: Engine = self._engine.sync_engine if self._is_async else self._engine
        return engine

    async def run_blocking(
        self,
        fn: Callable[..., T],
        *args: Any,  # noqa: ANN401  passed through to fn
    ) -> T:
        """Run a blocking database call in a worker thread so the event loop stays free.

        An engine on a single-connection pool runs the call in place instead.
        """
        if isinstance(self.sync_engine.pool, _SINGLE_CONNECTION_POOLS):
            return fn(*args)
        return await run_in_threadpool(fn, *args)

    @property
    def metadata(self) -> MetaData:
        """Get the metadata."""
        return self._metadata

    @property
    def registry(self) -> registry:
        """Get the registry."""
        return self._registry

    @property
    def is_async(self) -> bool:
        return self._is_async

    def table_name_for(self, base_name: str) -> str:
        """The table name to use; test isolation gives every mapping a fresh one."""
        if self._use_test_isolation:
            return _state.unique_table_name(base_name)
        return base_name

    def create_tables_now(self) -> None:
        """Create missing tables on a sync engine; async engines wait for the loop."""
        if not self._is_async:
            self._metadata.create_all(self._engine)
