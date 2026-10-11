"""Engine, registry and metadata holder for one LightApi app."""

from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import registry

logger = logging.getLogger(__name__)


class _GlobalState:
    """Process-wide SQLAlchemy metadata/registry, plus a thread-local copy.

    Every non-isolated SessionManager shares the one `metadata`/`registry`
    pair below. `use_test_isolation=True` gets a separate pair per thread
    instead (plus per-thread table-name counters), so tests running in
    parallel don't map two different classes onto the same table name.
    """

    def __init__(self) -> None:
        self._local = threading.local()
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
        if not hasattr(self._local, "metadata"):
            self._local.metadata = MetaData()
        return self._local.metadata

    @property
    def test_registry(self) -> registry:
        if not hasattr(self._local, "registry"):
            self._local.registry = registry(metadata=self.test_metadata)
        return self._local.registry

    def unique_table_name(self, base_name: str) -> str:
        """A table name unique to this thread, for parallel test isolation."""
        if not hasattr(self._local, "table_counter"):
            self._local.table_counter = {}
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

    def __init__(self, engine: Any, use_test_isolation: bool = False) -> None:
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
    def engine(self) -> Any:
        """Get the engine."""
        return self._engine

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
