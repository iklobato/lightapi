"""Session management abstraction for LightAPI.

Replaces the global registry pattern with proper dependency injection.
Provides both sync and async session management with proper cleanup.
"""

from __future__ import annotations

import contextlib
import threading
from typing import Any, Protocol, Union, runtime_checkable

from sqlalchemy import MetaData
from sqlalchemy.orm import Session, registry

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


def clear_test_registries():
    """Clear test-specific registries and metadata."""
    if hasattr(_thread_local, "metadata"):
        delattr(_thread_local, "metadata")
    if hasattr(_thread_local, "registry"):
        _thread_local.registry.dispose()
        delattr(_thread_local, "registry")
    if hasattr(_thread_local, "table_counter"):
        delattr(_thread_local, "table_counter")


# Global shared metadata for all endpoints (backward compatibility)
_GLOBAL_METADATA = MetaData()
_GLOBAL_REGISTRY = registry(metadata=_GLOBAL_METADATA)


class EngineProtocol(Protocol):
    """Protocol for SQLAlchemy engines (sync or async)."""

    def dispose(self) -> None: ...

    @property
    def url(self) -> Any: ...


@runtime_checkable
class AsyncEngineProtocol(Protocol):
    """Protocol for SQLAlchemy async engines."""

    def dispose(self) -> None: ...

    @property
    def url(self) -> Any: ...

    @property
    def sync_engine(self) -> Any: ...


EngineType = Union[EngineProtocol, AsyncEngineProtocol, Any]


class SessionManager:
    """Manages SQLAlchemy sessions and registry for LightAPI.

    Replaces the global registry pattern with instance-based management.
    Supports both sync and async engines.
    """

    def __init__(self, engine: EngineType, use_test_isolation: bool = False) -> None:
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
    def engine(self) -> EngineType:
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
        """Check if engine is async."""
        return self._is_async

    def get_registry_and_metadata(self) -> tuple[registry, MetaData]:
        """Get registry and metadata (compatibility with old API)."""
        return self._registry, self._metadata

    @contextlib.contextmanager
    def session(self):
        """Get a sync session context manager.

        Yields:
            SQLAlchemy Session
        """
        if self._is_async:
            # For async engines, use the sync engine
            from sqlalchemy.ext.asyncio import AsyncEngine

            async_engine = self._engine
            if isinstance(async_engine, AsyncEngine):
                engine = async_engine.sync_engine
            else:
                raise TypeError(f"Expected AsyncEngine, got {type(async_engine)}")
        else:
            engine = self._engine

        with Session(engine) as session:
            yield session

    @contextlib.asynccontextmanager
    async def async_session(self):
        """Get an async session context manager.

        Yields:
            SQLAlchemy AsyncSession
        """
        if not self._is_async:
            raise TypeError("Cannot create async session from sync engine")

        from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

        if not isinstance(self._engine, AsyncEngine):
            raise TypeError(f"Expected AsyncEngine, got {type(self._engine)}")

        async with AsyncSession(self._engine) as session:
            yield session

    def dispose(self) -> None:
        """Dispose the engine."""
        self._engine.dispose()


class LoginValidator:
    """Manages login validation functions."""

    def __init__(self, validator: Any = None) -> None:
        """Initialize with optional validator function.

        Args:
            validator: Function that accepts (username, password) and returns
                      user payload dict or None
        """
        self._validator = validator

    def set_validator(self, validator: Any) -> None:
        """Set the validator function."""
        self._validator = validator

    def get_validator(self) -> Any:
        """Get the validator function."""
        return self._validator

    def __call__(self, username: str, password: str) -> dict[str, Any] | None:
        """Validate credentials using the registered validator.

        Args:
            username: Username
            password: Password

        Returns:
            User payload dict or None if validation fails
        """
        if self._validator is None:
            return None
        return self._validator(username, password)
