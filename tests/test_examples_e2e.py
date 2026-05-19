"""End-to-end tests that load each example via runpy and exercise the
HTTP flow documented in its module docstring.

These guard against future regressions in the example scripts themselves
(not just clones of them) — if an example breaks, the corresponding test
fails.
"""

from __future__ import annotations

import os
import runpy
import warnings
from pathlib import Path

import pytest

from lightapi.lightapi import LightApi

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.fixture(autouse=True)
def _stub_run(monkeypatch):
    """Prevent example __main__ blocks from starting uvicorn."""
    monkeypatch.setattr(LightApi, "run", lambda self, *a, **kw: None)
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: None)


@pytest.fixture(autouse=True)
def _reset_global_registry():
    """Reset the global SQLAlchemy registry/metadata between examples.

    Each example defines its own endpoint classes (often named BookEndpoint),
    and SQLAlchemy's imperative-mapping registry is process-global. Without
    this reset, the second example would try to map a different class onto
    the same table name and inherit columns from the previous example.
    """
    from sqlalchemy import MetaData
    from sqlalchemy.orm import registry as sa_registry

    from lightapi import session_manager as sm

    sm._GLOBAL_METADATA = MetaData()
    sm._GLOBAL_REGISTRY = sa_registry(metadata=sm._GLOBAL_METADATA)
    yield


def _load(example_filename: str) -> LightApi:
    """Run an example __main__ block and return the LightApi instance it built."""
    captured: dict = {}

    original_run = LightApi.run

    def capture(self, *a, **kw):
        captured["app"] = self

    LightApi.run = capture
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            runpy.run_path(str(EXAMPLES_DIR / example_filename), run_name="__main__")
    finally:
        LightApi.run = original_run

    if "app" not in captured:
        raise RuntimeError(f"{example_filename} did not call LightApi.run")
    return captured["app"]


def _client(example_filename: str):
    """Build a TestClient for the example, entered as a context manager."""
    from starlette.testclient import TestClient

    app = _load(example_filename)
    return TestClient(app.build_app())


# ─── 01_minimal ──────────────────────────────────────────────────────────────


def test_example_01_minimal_full_crud():
    with _client("01_minimal.py") as c:
        r = c.post("/books", json={"title": "Clean Code", "author": "Martin"})
        assert r.status_code == 201
        book = r.json()

        assert c.get("/books").status_code == 200
        assert c.get(f"/books/{book['id']}").status_code == 200

        r = c.put(
            f"/books/{book['id']}",
            json={"title": "Clean Code v2", "author": "Martin", "version": book["version"]},
        )
        assert r.status_code == 200

        assert c.delete(f"/books/{book['id']}").status_code == 204
        assert c.get(f"/books/{book['id']}").status_code == 404


# ─── 02_crud ─────────────────────────────────────────────────────────────────


def test_example_02_crud_full_flow_with_optimistic_locking():
    with _client("02_crud.py") as c:
        r = c.post(
            "/books",
            json={"title": "Clean Code", "author": "Robert C. Martin", "price": 49.99},
        )
        assert r.status_code == 201
        book = r.json()
        assert book["version"] == 1

        r = c.put(
            f"/books/{book['id']}",
            json={
                "title": "Clean Code",
                "author": "Robert C. Martin",
                "price": 54.99,
                "published": True,
                "version": book["version"],
            },
        )
        assert r.status_code == 200
        assert r.json()["version"] == 2

        r = c.patch(
            f"/books/{book['id']}",
            json={"price": 59.99, "version": 2},
        )
        assert r.status_code == 200
        assert r.json()["price"] == 59.99

        # Stale version → 409 Conflict
        r = c.put(
            f"/books/{book['id']}",
            json={
                "title": "X",
                "author": "Y",
                "price": 1.0,
                "published": True,
                "version": 1,
            },
        )
        assert r.status_code == 409

        assert c.delete(f"/books/{book['id']}").status_code == 204


# ─── 03_auth_jwt ─────────────────────────────────────────────────────────────


def test_example_03_jwt_login_then_protected_call():
    with _client("03_auth_jwt.py") as c:
        # Unauthenticated → 401
        assert c.get("/books").status_code == 401

        # Bad credentials → 401
        assert (
            c.post(
                "/auth/login", json={"username": "admin", "password": "wrong"}
            ).status_code
            == 401
        )

        # Good login → token
        r = c.post("/auth/login", json={"username": "admin", "password": "secret"})
        assert r.status_code == 200
        token = r.json()["token"]

        # Authenticated GET → 200
        r = c.get("/books", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

        # Authenticated POST → 201
        r = c.post(
            "/books",
            json={"title": "T", "author": "A", "price": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201


# ─── 04_auth_basic ───────────────────────────────────────────────────────────


def test_example_04_basic_auth_flow():
    with _client("04_auth_basic.py") as c:
        # No credentials → 401
        assert c.get("/books").status_code == 401

        # Wrong credentials → 401 (Basic of "wrong:wrong")
        assert (
            c.get(
                "/books", headers={"Authorization": "Basic d3Jvbmc6d3Jvbmc="}
            ).status_code
            == 401
        )

        # Valid Basic header (admin:secret) → 200
        r = c.get("/books", headers={"Authorization": "Basic YWRtaW46c2VjcmV0"})
        assert r.status_code == 200


# ─── 05_permissions ──────────────────────────────────────────────────────────


def test_example_05_permission_matrix():
    os.environ["LIGHTAPI_JWT_SECRET"] = "secret"
    with _client("05_permissions.py") as c:
        # Public: no auth required
        assert c.get("/public").status_code == 200

        # Private: needs JWT
        assert c.get("/private").status_code == 401

        # Admin: needs JWT (will be 401 without token, 403 with non-admin token)
        assert c.get("/admin").status_code == 401

        # Get admin token via login
        r = c.post("/auth/login", json={"username": "admin", "password": "secret"})
        admin_token = r.json()["token"]

        assert (
            c.get(
                "/private", headers={"Authorization": f"Bearer {admin_token}"}
            ).status_code
            == 200
        )
        assert (
            c.get(
                "/admin", headers={"Authorization": f"Bearer {admin_token}"}
            ).status_code
            == 200
        )

        # Non-admin token → /admin returns 403
        r = c.post("/auth/login", json={"username": "user", "password": "password"})
        user_token = r.json()["token"]
        assert (
            c.get(
                "/admin", headers={"Authorization": f"Bearer {user_token}"}
            ).status_code
            == 403
        )
        assert (
            c.get(
                "/private", headers={"Authorization": f"Bearer {user_token}"}
            ).status_code
            == 200
        )


# ─── 06_pagination_page ──────────────────────────────────────────────────────


def test_example_06_page_pagination_response_envelope():
    with _client("06_pagination_page.py") as c:
        # Seed 6 books → page_size=5 → 2 pages
        for i in range(6):
            assert (
                c.post(
                    "/books",
                    json={
                        "title": f"B{i}",
                        "author": f"A{i}",
                        "price": float(i * 10),
                    },
                ).status_code
                == 201
            )

        r = c.get("/books")
        body = r.json()
        assert r.status_code == 200
        # Page-number envelope keys
        assert "results" in body
        assert "count" in body or "pages" in body or "total" in body

        r = c.get("/books?page=2")
        assert r.status_code == 200
        body = r.json()
        assert "results" in body


# ─── 07_pagination_cursor ────────────────────────────────────────────────────


def test_example_07_cursor_pagination():
    with _client("07_pagination_cursor.py") as c:
        for i in range(3):
            assert c.post("/books", json={"title": f"B{i}", "author": f"A{i}"}).status_code == 201
        r = c.get("/books")
        assert r.status_code == 200
        body = r.json()
        assert "results" in body


# ─── 08_filtering ────────────────────────────────────────────────────────────


def test_example_08_filtering_search_and_ordering():
    with _client("08_filtering.py") as c:
        c.post(
            "/books",
            json={
                "title": "Clean Code",
                "author": "Martin",
                "genre": "Programming",
                "price": 40,
            },
        )
        c.post(
            "/books",
            json={
                "title": "Foundation",
                "author": "Asimov",
                "genre": "Fiction",
                "price": 15,
            },
        )
        c.post(
            "/books",
            json={
                "title": "Dune",
                "author": "Herbert",
                "genre": "Fiction",
                "price": 20,
            },
        )

        # FieldFilter: ?genre=Fiction
        r = c.get("/books?genre=Fiction")
        titles = {b["title"] for b in r.json()["results"]}
        assert titles == {"Foundation", "Dune"}

        # SearchFilter: ?search=clean
        r = c.get("/books?search=clean")
        titles = [b["title"] for b in r.json()["results"]]
        assert "Clean Code" in titles

        # OrderingFilter: ?ordering=price ascending
        r = c.get("/books?ordering=price")
        titles = [b["title"] for b in r.json()["results"]]
        assert titles == ["Foundation", "Dune", "Clean Code"]

        # ?ordering=-price descending
        r = c.get("/books?ordering=-price")
        titles = [b["title"] for b in r.json()["results"]]
        assert titles == ["Clean Code", "Dune", "Foundation"]

        # Combined
        r = c.get("/books?genre=Fiction&ordering=-price")
        titles = [b["title"] for b in r.json()["results"]]
        assert titles == ["Dune", "Foundation"]


# ─── 09_caching ──────────────────────────────────────────────────────────────


def test_example_09_caching_basic_crud_still_works():
    """When Redis is unavailable, cache is silently skipped and CRUD still works."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with _client("09_caching.py") as c:
            assert c.get("/books").status_code == 200
            assert (
                c.post(
                    "/books", json={"title": "X", "author": "Y", "price": 10}
                ).status_code
                == 201
            )
            assert c.get("/books").status_code == 200


# ─── 10_async ────────────────────────────────────────────────────────────────


def test_example_10_async_full_crud():
    with _client("10_async.py") as c:
        r = c.post(
            "/books", json={"title": "Async Book", "author": "A", "price": 25}
        )
        assert r.status_code == 201
        book = r.json()

        assert c.get("/books").status_code == 200
        assert c.get(f"/books/{book['id']}").status_code == 200

        r = c.put(
            f"/books/{book['id']}",
            json={"title": "X", "author": "Y", "price": 30, "version": 1},
        )
        assert r.status_code == 200
        assert c.delete(f"/books/{book['id']}").status_code == 204


# ─── 11_mixed_sync_async ─────────────────────────────────────────────────────


def test_example_11_async_app_with_sync_and_async_endpoints():
    with _client("11_mixed_sync_async.py") as c:
        assert (
            c.post("/async-books", json={"title": "A", "author": "X"}).status_code
            == 201
        )
        assert c.get("/async-books").status_code == 200
        assert (
            c.post("/sync-books", json={"title": "S", "author": "Y"}).status_code
            == 201
        )
        assert c.get("/sync-books").status_code == 200


# ─── 12_queryset ─────────────────────────────────────────────────────────────


def test_example_12_custom_queryset_filters_by_query_param():
    with _client("12_queryset.py") as c:
        c.post(
            "/books",
            json={"title": "Cheap", "author": "A", "price": 10, "published": True},
        )
        c.post(
            "/books",
            json={"title": "Expensive", "author": "B", "price": 100, "published": True},
        )
        c.post(
            "/books",
            json={"title": "Draft", "author": "C", "price": 50, "published": False},
        )

        # Default: all 3 visible
        r = c.get("/books")
        assert len(r.json()["results"]) == 3

        # published_only=true → drops Draft
        r = c.get("/books?published_only=true")
        titles = {b["title"] for b in r.json()["results"]}
        assert titles == {"Cheap", "Expensive"}

        # min_price=50 → drops Cheap
        r = c.get("/books?min_price=50")
        titles = {b["title"] for b in r.json()["results"]}
        assert titles == {"Expensive", "Draft"}


# ─── 13_middleware ───────────────────────────────────────────────────────────


def test_example_13_middleware_adds_request_id_and_response_time():
    with _client("13_middleware.py") as c:
        r = c.get("/books")
        assert r.status_code == 200
        assert "X-Request-Id" in r.headers
        assert "X-Response-Time" in r.headers
        # request_id is a UUID
        rid = r.headers["X-Request-Id"]
        assert len(rid) == 36


# ─── 14_background ───────────────────────────────────────────────────────────


def test_example_14_background_task_returns_response_immediately():
    with _client("14_background.py") as c:
        r = c.post("/items", json={"name": "Test Item"})
        assert r.status_code == 201
        assert r.json()["name"] == "Test Item"
        assert c.get("/items").status_code == 200


# ─── 15_yaml_config ──────────────────────────────────────────────────────────


def test_example_15_yaml_config_loads_two_endpoints():
    # Cleanup any prior db before/after this test
    db_file = Path("example_15_yaml.db")
    if db_file.exists():
        db_file.unlink()
    try:
        with _client("15_yaml_config.py") as c:
            assert (
                c.post(
                    "/books", json={"title": "T", "author": "A", "price": 1.0}
                ).status_code
                == 201
            )
            assert c.get("/books").status_code == 200
            # bio is optional
            assert c.post("/authors", json={"name": "N"}).status_code == 201
            assert c.post("/authors", json={"name": "M", "bio": "B"}).status_code == 201
            assert c.get("/authors").status_code == 200
    finally:
        if db_file.exists():
            db_file.unlink()


# ─── 16_rate_limit ───────────────────────────────────────────────────────────


def test_example_16_rate_limit_auth_paths_exist():
    with _client("16_rate_limit.py") as c:
        # /dummy is JWT-protected → 401 without auth
        assert c.get("/dummy").status_code == 401
        # /auth/login responds (good credentials → 200)
        assert (
            c.post(
                "/auth/login", json={"username": "admin", "password": "secret"}
            ).status_code
            == 200
        )


# ─── 17_relationships ────────────────────────────────────────────────────────


def test_example_17_foreign_key_relationship():
    with _client("17_relationships.py") as c:
        r = c.post("/authors", json={"name": "John Doe"})
        assert r.status_code == 201
        author_id = r.json()["id"]

        r = c.post(
            "/books", json={"title": "Test Book", "author_id": author_id}
        )
        assert r.status_code == 201
        book = r.json()
        assert book["author_id"] == author_id

        assert c.get("/books").status_code == 200
        assert c.get("/authors").status_code == 200


# ─── 18_full_api ─────────────────────────────────────────────────────────────


def test_example_18_full_api_combines_features():
    os.environ["LIGHTAPI_JWT_SECRET"] = "secret"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with _client("18_full_api.py") as c:
            # Public books CRUD
            r = c.post(
                "/books",
                json={
                    "title": "T",
                    "author": "A",
                    "genre": "Programming",
                    "price": 30,
                    "published": True,
                },
            )
            assert r.status_code == 201
            # Middleware: X-Response-Time header
            assert "X-Response-Time" in r.headers

            # Authors requires JWT
            assert c.get("/authors").status_code == 401

            login = c.post(
                "/auth/login", json={"username": "admin", "password": "secret"}
            )
            assert login.status_code == 200
            token = login.json()["token"]
            assert (
                c.get(
                    "/authors", headers={"Authorization": f"Bearer {token}"}
                ).status_code
                == 200
            )

            # Public endpoint always accessible
            assert c.get("/public").status_code == 200


# ─── v2_quickstart ───────────────────────────────────────────────────────────


def test_example_v2_quickstart_basic_crud():
    db_file = Path("books.db")
    if db_file.exists():
        db_file.unlink()
    try:
        with _client("v2_quickstart.py") as c:
            r = c.post(
                "/books",
                json={
                    "title": "Clean Code",
                    "author": "Martin",
                    "genre": "Programming",
                    "published": True,
                },
            )
            assert r.status_code == 201
            assert c.get("/books").status_code == 200
            assert c.get("/books/1").status_code == 200
    finally:
        if db_file.exists():
            db_file.unlink()


# ─── v2_full_demo ────────────────────────────────────────────────────────────


def test_example_v2_full_demo_books_and_tags():
    os.environ["LIGHTAPI_JWT_SECRET"] = "demo-secret-key"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with _client("v2_full_demo.py") as c:
            r = c.post(
                "/books",
                json={
                    "title": "X",
                    "author": "Y",
                    "genre": "g",
                    "price": 10,
                    "published": True,
                },
            )
            assert r.status_code == 201
            assert c.get("/books").status_code == 200
            assert c.get("/tags").status_code == 200
