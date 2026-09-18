"""A plain `def get/post/...` override must be served, as the tutorial teaches."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
from lightapi.fields import Field as LField


class GreetingEndpoint(RestEndpoint):
    name: str = LField(min_length=1)

    def get(self, request: Request):
        return {"message": "custom sync get"}


class DecoratedListEndpoint(RestEndpoint):
    name: str = LField(min_length=1)

    def get(self, request: Request):
        response = self.list(request)
        response.headers["X-Served-By"] = "sync-override"
        return response


class AsyncEngineSyncOverrideEndpoint(RestEndpoint):
    name: str = LField(min_length=1)

    def get(self, request: Request):
        response = self.list(request)
        response.headers["X-Served-By"] = "sync-override"
        return response


class BlogEntryEndpoint(RestEndpoint):
    """`post` here is a column, not a verb override."""

    post: str = LField(min_length=1)


@pytest.fixture
def sync_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine)
    app.register(
        {
            "/greetings": GreetingEndpoint,
            "/decorated": DecoratedListEndpoint,
            "/blogentries": BlogEntryEndpoint,
        }
    )
    return TestClient(app.build_app())


@pytest_asyncio.fixture
async def async_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = LightApi(engine=engine, mode="async")
    app.register({"/asyncsyncoverride": AsyncEngineSyncOverrideEndpoint})
    async with AsyncClient(
        transport=ASGITransport(app=app.build_app()), base_url="http://test"
    ) as client:
        yield client
    await engine.dispose()


def test_sync_get_override_returning_dict_is_served(sync_client):
    response = sync_client.get("/greetings")

    assert response.status_code == 200
    assert response.json() == {"message": "custom sync get"}


def test_sync_get_override_can_call_the_builtin_list(sync_client):
    response = sync_client.get("/decorated")

    assert response.status_code == 200
    assert response.headers["X-Served-By"] == "sync-override"
    assert response.json() == {"results": []}


def test_column_named_like_a_verb_is_not_treated_as_an_override(sync_client):
    created = sync_client.post("/blogentries", json={"post": "hello"})

    assert created.status_code == 201
    assert created.json()["post"] == "hello"


async def test_sync_get_override_on_async_engine_can_call_the_builtin_list(
    async_client,
):
    response = await async_client.get("/asyncsyncoverride")

    assert response.status_code == 200
    assert response.headers["X-Served-By"] == "sync-override"
    assert response.json() == {"results": []}
