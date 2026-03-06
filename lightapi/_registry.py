"""App-level SQLAlchemy registry and metadata singleton.

This module holds the global registry, metadata, and engine used by
RestEndpointMeta._map_imperatively() and RestEndpoint CRUD methods.
The engine is injected by LightApi.run() before requests start.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import registry

_registry: registry | None = None
_metadata: MetaData | None = None
_engine: object | None = None


def get_registry_and_metadata() -> tuple[registry, MetaData]:
    global _registry, _metadata
    if _registry is None or _metadata is None:
        _metadata = MetaData()
        _registry = registry(metadata=_metadata)
    return _registry, _metadata


def set_engine(engine: object) -> None:
    global _engine
    _engine = engine


def get_engine() -> object:
    if _engine is None:
        raise RuntimeError(
            "No engine configured. Call LightApi(engine=...) or ensure "
            "database connection is set before the first request."
        )
    return _engine
