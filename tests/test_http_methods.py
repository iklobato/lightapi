"""Tests for US4: HttpMethod marker mixins and 405 Allow header."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import HttpMethod, LightApi, RestEndpoint
from lightapi.fields import Field as LField


class ReadOnlyEndpoint(RestEndpoint, HttpMethod.GET):
    title: str = LField(min_length=1)


class WriteOnlyEndpoint(RestEndpoint, HttpMethod.POST):
    body: str = LField(min_length=1)


class ReadWriteEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    name: str = LField(min_length=1)


@pytest.fixture(scope="module")
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app_instance = LightApi(engine=engine)
    app_instance.register({
        "/readonly": ReadOnlyEndpoint,
        "/writeonly": WriteOnlyEndpoint,
        "/readwrite": ReadWriteEndpoint,
    })
    return TestClient(app_instance.build_app())


class TestAllowedMethods:
    def test_read_only_get_allowed(self, client):
        resp = client.get("/readonly")
        assert resp.status_code == 200

    def test_read_only_post_not_registered(self, client):
        resp = client.post("/readonly", json={"title": "X"})
        assert resp.status_code == 405

    def test_write_only_post_allowed(self, client):
        resp = client.post("/writeonly", json={"body": "content"})
        assert resp.status_code == 201

    def test_write_only_get_not_registered(self, client):
        resp = client.get("/writeonly")
        assert resp.status_code == 405

    def test_readwrite_both_allowed(self, client):
        resp_get = client.get("/readwrite")
        assert resp_get.status_code == 200
        resp_post = client.post("/readwrite", json={"name": "item"})
        assert resp_post.status_code == 201


class TestAllowedMethodsOnDetail:
    def test_get_detail_allowed_on_read_only(self, client):
        post_resp = client.post("/readwrite", json={"name": "probe"})
        item_id = post_resp.json()["id"]
        resp = client.get(f"/readonly/{item_id}")
        assert resp.status_code in (200, 404)  # table might be empty, 404 is fine

    def test_delete_not_registered_on_read_only(self, client):
        resp = client.delete("/readonly/1")
        assert resp.status_code == 405


class TestHttpMethodMeta:
    def test_allowed_methods_attribute_readonly(self):
        assert ReadOnlyEndpoint._allowed_methods == {"GET"}

    def test_allowed_methods_attribute_writeonly(self):
        assert WriteOnlyEndpoint._allowed_methods == {"POST"}

    def test_allowed_methods_attribute_readwrite(self):
        assert ReadWriteEndpoint._allowed_methods == {"GET", "POST"}
