"""App-level SQLAlchemy registry and metadata singleton.

This module holds the global registry, metadata, and engine used by
RestEndpointMeta._map_imperatively() and RestEndpoint CRUD methods.
The engine is injected by LightApi.run() before requests start.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from sqlalchemy import MetaData
from sqlalchemy.orm import registry

LoginValidator = Callable[[str, str], dict[str, Any] | None]

_state: dict[str, object | None] = {
    "registry": None,
    "metadata": None,
    "engine": None,
    "login_validator": None,
}


def get_registry_and_metadata() -> tuple[registry, MetaData]:
    reg = cast(registry | None, _state["registry"])
    meta = cast(MetaData | None, _state["metadata"])
    if reg is None or meta is None:
        meta = MetaData()
        reg = registry(metadata=meta)
        _state["metadata"] = meta
        _state["registry"] = reg
    return reg, meta


def set_engine(engine: object) -> None:
    _state["engine"] = engine


def get_engine() -> object:
    engine = _state["engine"]
    if engine is None:
        raise RuntimeError(
            "No engine configured. Call LightApi(engine=...) or ensure "
            "database connection is set before the first request."
        )
    return engine


def set_login_validator(validator: LoginValidator) -> None:
    _state["login_validator"] = validator


def get_login_validator() -> LoginValidator | None:
    validator = _state["login_validator"]
    if validator is None:
        return None
    return cast(LoginValidator, validator)
