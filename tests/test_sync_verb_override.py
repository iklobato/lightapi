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


class AllVerbsEndpoint(RestEndpoint):
    """A sync override for every verb, each stamping a header so the test can
    tell the override ran rather than the built-in method."""

    name: str = LField(min_length=1)

    def post(self, request: Request):
        response = self.create({"name": "from-post-override"})
        response.headers["X-Served-By"] = "post-override"
        return response

    def put(self, request: Request):
        pk = request.path_params["id"]
        response = self.update({"name": "from-put-override", "version": 1}, pk)
        response.headers["X-Served-By"] = "put-override"
        return response

    def patch(self, request: Request):
        pk = request.path_params["id"]
        response = self.update(
            {"name": "from-patch-override", "version": 1}, pk, partial=True
        )
        response.headers["X-Served-By"] = "patch-override"
        return response

    def delete(self, request: Request):
        pk = request.path_params["id"]
        response = self.destroy(request, pk)
        response.headers["X-Served-By"] = "delete-override"
        return response


class DetailGetOverrideEndpoint(RestEndpoint):
    """A sync `def get` override also intercepts the detail route (/x/{id})."""

    name: str = LField(min_length=1)

    def get(self, request: Request):
        pk = request.path_params.get("id")
        if pk is None:
            return self.list(request)
        response = self.retrieve(request, pk)
        response.headers["X-Served-By"] = "get-override"
        return response


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
            "/allverbs": AllVerbsEndpoint,
            "/detailget": DetailGetOverrideEndpoint,
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


def test_sync_post_override_is_served(sync_client):
    response = sync_client.post("/allverbs", json={"name": "ignored"})

    assert response.status_code == 201
    assert response.headers["X-Served-By"] == "post-override"
    assert response.json()["name"] == "from-post-override"


def test_sync_put_override_is_served(sync_client):
    sync_client.post("/allverbs", json={"name": "original"})

    response = sync_client.put("/allverbs/1", json={"name": "ignored", "version": 1})

    assert response.status_code == 200
    assert response.headers["X-Served-By"] == "put-override"
    assert response.json()["name"] == "from-put-override"


def test_sync_patch_override_is_served(sync_client):
    sync_client.post("/allverbs", json={"name": "original"})

    response = sync_client.patch("/allverbs/1", json={"version": 1})

    assert response.status_code == 200
    assert response.headers["X-Served-By"] == "patch-override"
    assert response.json()["name"] == "from-patch-override"


def test_sync_delete_override_is_served(sync_client):
    sync_client.post("/allverbs", json={"name": "original"})

    response = sync_client.delete("/allverbs/1")

    assert response.status_code == 204
    assert response.headers["X-Served-By"] == "delete-override"


def test_sync_get_override_also_intercepts_the_detail_route(sync_client):
    created = sync_client.post("/detailget", json={"name": "x"}).json()

    response = sync_client.get(f"/detailget/{created['id']}")

    assert response.status_code == 200
    assert response.headers["X-Served-By"] == "get-override"
    assert response.json()["name"] == "x"
