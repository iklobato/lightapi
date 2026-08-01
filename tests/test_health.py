"""The always-on /healthz probe route."""

from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint


def _client() -> TestClient:
    class Item(RestEndpoint):
        name: str = Field(min_length=1)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine)
    app.register({"/items": Item})
    return TestClient(app.build_app())


def test_healthz_returns_ok() -> None:
    resp = _client().get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
