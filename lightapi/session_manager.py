"""Engine, registry and metadata holder for one LightApi app."""

from __future__ import annotations

import threading
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import registry

# Thread-local storage for test isolation
_thread_local = threading.local()


def _get_test_metadata():
    """Get or create test-specific metadata."""
    if not hasattr(_thread_local, "metadata"):
        _thread_local.metadata = MetaData()
    return _thread_local.metadata


def _get_test_registry():
    """Get or create test-specific registry."""
    if not hasattr(_thread_local, "registry"):
        _thread_local.registry = registry(metadata=_get_test_metadata())
    return _thread_local.registry


def get_unique_table_name(base_name: str) -> str:
    """Get a unique table name for test isolation."""
    import logging

    logger = logging.getLogger(__name__)

    if not hasattr(_thread_local, "table_counter"):
        _thread_local.table_counter = {}

    if base_name not in _thread_local.table_counter:
        _thread_local.table_counter[base_name] = 0

    _thread_local.table_counter[base_name] += 1
    counter = _thread_local.table_counter[base_name]

    # For the first table, use the base name, for subsequent ones add counter
    if counter == 1:
        result = base_name
    else:
        result = f"{base_name}_{counter}"

    logger.debug(f"get_unique_table_name: {base_name} -> {result} (counter: {counter})")
    return result


# Global shared metadata for all endpoints (backward compatibility)
_GLOBAL_METADATA = MetaData()
_GLOBAL_REGISTRY = registry(metadata=_GLOBAL_METADATA)


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
            self._metadata = _get_test_metadata()
            self._registry = _get_test_registry()
        else:
            self._metadata = _GLOBAL_METADATA
            self._registry = _GLOBAL_REGISTRY

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
