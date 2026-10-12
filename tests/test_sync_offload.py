"""Sync CRUD must not run on the event loop thread, except on single-connection pools."""

import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy import select as sa_select
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
from lightapi.core import Middleware
from lightapi.fields import Field as LField

threads: dict[str, int] = {}


class RecordLoopThread(Middleware):
    async def process(
        self, request: Request, response: Response | None
    ) -> Response | None:
        if response is None:
            threads["loop"] = threading.get_ident()
        return response


class PooledProbe(RestEndpoint):
    label: str = LField(min_length=1)

    def queryset(self, request: Request):
        threads["crud"] = threading.get_ident()
        return sa_select(type(self)._model_class)


class StaticProbe(RestEndpoint):
    label: str = LField(min_length=1)

    def queryset(self, request: Request):
        threads["crud"] = threading.get_ident()
        return sa_select(type(self)._model_class)


@pytest.fixture(autouse=True)
def reset_threads():
    threads.clear()


def _client(engine, route: str, endpoint: type) -> TestClient:
    app = LightApi(engine=engine, middlewares=[RecordLoopThread])
    app.register({route: endpoint})
    return TestClient(app.build_app())


def test_sync_list_on_pooled_engine_runs_off_the_event_loop_thread(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'offload.db'}")
    client = _client(engine, "/pooledprobes", PooledProbe)

    response = client.get("/pooledprobes")

    assert response.status_code == 200
    assert threads["crud"] != threads["loop"]


def test_sync_list_on_static_pool_stays_on_the_event_loop_thread():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    client = _client(engine, "/staticprobes", StaticProbe)

    response = client.get("/staticprobes")

    assert response.status_code == 200
    assert threads["crud"] == threads["loop"]
