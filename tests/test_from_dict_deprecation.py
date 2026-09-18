"""LightApi.from_dict still works, and says it is going away."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import LightApi


def _config() -> dict:
    return {"endpoints": {"/dictpamphlets": {"fields": {"title": str}}}}


def _engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_from_dict_warns_about_its_removal():
    with pytest.warns(DeprecationWarning, match="from_dict.*0.2.0"):
        LightApi.from_dict(_config(), engine=_engine())


def test_from_dict_still_builds_a_working_app():
    with pytest.warns(DeprecationWarning):
        app = LightApi.from_dict(_config(), engine=_engine())
    client = TestClient(app.build_app())

    created = client.post("/dictpamphlets", json={"title": "still here"})

    assert created.status_code == 201
    assert created.json()["title"] == "still here"
