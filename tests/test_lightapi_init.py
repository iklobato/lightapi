"""Tests for LightApi initialization with engine/database_url/env vars."""

import pytest

from lightapi import LightApi
from lightapi.exceptions import ConfigurationError


def test_lightapi_without_args_uses_lightapi_database_url_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LightApi() without args uses LIGHTAPI_DATABASE_URL when set."""
    monkeypatch.setenv("LIGHTAPI_DATABASE_URL", "sqlite:///:memory:")
    app = LightApi()
    assert app._engine is not None
    assert "sqlite" in str(app._engine.url)


def test_lightapi_without_args_raises_when_no_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LightApi() raises ConfigurationError when LIGHTAPI_DATABASE_URL is unset."""
    monkeypatch.delenv("LIGHTAPI_DATABASE_URL", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        LightApi()
    assert "No database configured" in str(exc_info.value)
    assert "LIGHTAPI_DATABASE_URL" in str(exc_info.value)


def test_lightapi_with_database_url_param() -> None:
    """LightApi(database_url=...) creates engine from param."""
    app = LightApi(database_url="sqlite:///:memory:")
    assert app._engine is not None
    assert "sqlite" in str(app._engine.url)


def test_lightapi_with_engine_param() -> None:
    """LightApi(engine=...) uses provided engine."""
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:")
    app = LightApi(engine=engine)
    assert app._engine is engine
