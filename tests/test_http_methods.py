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
    app_instance.register(
        {
            "/readonly": ReadOnlyEndpoint,
            "/writeonly": WriteOnlyEndpoint,
            "/readwrite": ReadWriteEndpoint,
        }
    )
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


class Test405AllowHeader:
    def test_405_includes_allow_header(self, client):
        """PUT on read-only endpoint returns 405 with Allow: GET header (FR-11)."""
        resp = client.put("/readonly/1", json={"title": "X"})
        assert resp.status_code == 405
        assert "Allow" in resp.headers
        assert "GET" in resp.headers["Allow"]


class TestRouteMerge:
    def test_route_merge_combines_methods(self, client):
        """ReadWriteEndpoint on /readwrite accepts both GET and POST."""
        resp_get = client.get("/readwrite")
        assert resp_get.status_code == 200
        resp_post = client.post("/readwrite", json={"name": "merged"})
        assert resp_post.status_code == 201


class TestDuplicateRouteRegistration:
    def test_same_route_same_verb_twice_overwrites(self, client):
        """Registering two classes for same path: current API overwrites (no ConfigurationError)."""
        # The register() API takes one class per path; duplicate keys in dict not possible.
        # Second register() call would add duplicate routes - framework may or may not raise.
        # This test documents current behavior: second registration overwrites _endpoint_map.
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine)
        app.register({"/dup": ReadOnlyEndpoint})
        app.register({"/dup": WriteOnlyEndpoint})  # overwrites
        assert app._endpoint_map["/dup"] is WriteOnlyEndpoint
