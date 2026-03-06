"""Integration tests for US1: CRUD auto-generation."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
from lightapi.fields import Field as LField


class BookEndpoint(RestEndpoint):
    title: str = LField(min_length=1)
    author: str = LField(min_length=1)


@pytest.fixture(scope="module")
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app_instance = LightApi(engine=engine)
    app_instance.register({"/books": BookEndpoint})
    app = app_instance.build_app()
    return TestClient(app)


class TestGETCollection:
    def test_empty_list_returns_200_with_results_key(self, client):
        resp = client.get("/books")
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body
        assert body["results"] == []

    def test_after_create_list_returns_item(self, client):
        client.post("/books", json={"title": "Clean Code", "author": "Robert Martin"})
        resp = client.get("/books")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert any(r["title"] == "Clean Code" for r in results)


class TestPOST:
    def test_create_returns_201(self, client):
        resp = client.post("/books", json={"title": "Refactoring", "author": "Fowler"})
        assert resp.status_code == 201

    def test_create_returns_id(self, client):
        resp = client.post("/books", json={"title": "DDD", "author": "Evans"})
        assert resp.json()["id"] is not None

    def test_create_validation_error_422(self, client):
        resp = client.post("/books", json={"title": "", "author": "X"})
        assert resp.status_code == 422

    def test_create_missing_field_422(self, client):
        resp = client.post("/books", json={"title": "Only title"})
        assert resp.status_code == 422

    def test_create_includes_auto_fields(self, client):
        resp = client.post("/books", json={"title": "SICP", "author": "Abelson"})
        body = resp.json()
        assert "version" in body
        assert body["version"] == 1


class TestGETDetail:
    def test_retrieve_existing(self, client):
        post_resp = client.post("/books", json={"title": "TDD", "author": "Beck"})
        book_id = post_resp.json()["id"]
        resp = client.get(f"/books/{book_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == book_id

    def test_retrieve_nonexistent_404(self, client):
        resp = client.get("/books/999999")
        assert resp.status_code == 404


class TestPUT:
    def test_update_returns_200(self, client):
        post_resp = client.post(
            "/books", json={"title": "Original", "author": "Author"}
        )
        book = post_resp.json()
        resp = client.put(
            f"/books/{book['id']}",
            json={"title": "Updated", "author": "Author", "version": book["version"]},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

    def test_update_increments_version(self, client):
        post_resp = client.post("/books", json={"title": "V1", "author": "Auth"})
        book = post_resp.json()
        put_resp = client.put(
            f"/books/{book['id']}",
            json={"title": "V2", "author": "Auth", "version": book["version"]},
        )
        assert put_resp.json()["version"] == book["version"] + 1

    def test_update_version_conflict_409(self, client):
        post_resp = client.post("/books", json={"title": "Conflict", "author": "Auth"})
        book = post_resp.json()
        resp = client.put(
            f"/books/{book['id']}",
            json={"title": "Bad", "author": "Auth", "version": 9999},
        )
        assert resp.status_code == 409

    def test_update_missing_version_422(self, client):
        post_resp = client.post("/books", json={"title": "NoVer", "author": "Auth"})
        book = post_resp.json()
        resp = client.put(f"/books/{book['id']}", json={"title": "X", "author": "Y"})
        assert resp.status_code == 422

    def test_update_nonexistent_404(self, client):
        resp = client.put(
            "/books/999999", json={"title": "X", "author": "Y", "version": 1}
        )
        assert resp.status_code == 404


class TestPATCH:
    def test_patch_partial_update_returns_200(self, client):
        post_resp = client.post(
            "/books", json={"title": "Original", "author": "Author"}
        )
        book = post_resp.json()
        resp = client.patch(
            f"/books/{book['id']}",
            json={"title": "New", "version": book["version"]},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"
        assert resp.json()["author"] == "Author"

    def test_patch_version_conflict_409(self, client):
        post_resp = client.post("/books", json={"title": "Conflict", "author": "Auth"})
        book = post_resp.json()
        resp = client.patch(
            f"/books/{book['id']}",
            json={"title": "Bad", "version": 9999},
        )
        assert resp.status_code == 409

    def test_patch_missing_version_422(self, client):
        post_resp = client.post("/books", json={"title": "NoVer", "author": "Auth"})
        book = post_resp.json()
        resp = client.patch(f"/books/{book['id']}", json={"title": "X"})
        assert resp.status_code == 422

    def test_patch_nonexistent_404(self, client):
        resp = client.patch(
            "/books/999999",
            json={"title": "X", "version": 1},
        )
        assert resp.status_code == 404


class TestDELETE:
    def test_delete_returns_204(self, client):
        post_resp = client.post("/books", json={"title": "ToDelete", "author": "X"})
        book_id = post_resp.json()["id"]
        resp = client.delete(f"/books/{book_id}")
        assert resp.status_code == 204

    def test_delete_nonexistent_404(self, client):
        resp = client.delete("/books/999999")
        assert resp.status_code == 404

    def test_after_delete_retrieve_404(self, client):
        post_resp = client.post("/books", json={"title": "Gone", "author": "Y"})
        book_id = post_resp.json()["id"]
        client.delete(f"/books/{book_id}")
        resp = client.get(f"/books/{book_id}")
        assert resp.status_code == 404


class TestErrorResponseFormats:
    """Verify exact error response formats per spec."""

    def test_404_detail_not_found(self, client):
        resp = client.get("/books/999999")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "not found"}

    def test_409_detail_version_conflict(self, client):
        post_resp = client.post("/books", json={"title": "Conflict", "author": "Auth"})
        book = post_resp.json()
        resp = client.put(
            f"/books/{book['id']}",
            json={"title": "Bad", "author": "Auth", "version": 9999},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "version conflict"

    def test_422_pydantic_format(self, client):
        resp = client.post("/books", json={"title": "", "author": "X"})
        assert resp.status_code == 422
        body = resp.json()
        assert "detail" in body
        assert isinstance(body["detail"], list)
        assert len(body["detail"]) >= 1
        err = body["detail"][0]
        assert "loc" in err
        assert "msg" in err
        assert "type" in err
