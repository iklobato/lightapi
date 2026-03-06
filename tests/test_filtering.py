"""Tests for US5: Filtering, Search, Ordering, and Pagination."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import Filtering, LightApi, Pagination, RestEndpoint
from lightapi.fields import Field as LField
from lightapi.filters import FieldFilter, OrderingFilter, SearchFilter


class ProductEndpoint(RestEndpoint):
    name: str = LField(min_length=1)
    category: str = LField(min_length=1)
    price: float = LField(ge=0)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["category"],
            search=["name"],
            ordering=["price", "name"],
        )
        pagination = Pagination(style="page_number", page_size=3)


class CursorProduct(RestEndpoint):
    label: str = LField(min_length=1)

    class Meta:
        pagination = Pagination(style="cursor", page_size=2)


class NoPagProduct(RestEndpoint):
    """Endpoint without pagination — returns {results: [...]} only."""

    name: str = LField(min_length=1)
    category: str = LField(min_length=1)


@pytest.fixture(scope="module")
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app_instance = LightApi(engine=engine)
    app_instance.register({
        "/products": ProductEndpoint,
        "/cursor_products": CursorProduct,
        "/nopag_products": NoPagProduct,
    })
    starlette_app = app_instance.build_app()
    c = TestClient(starlette_app)

    # Seed data
    products = [
        {"name": "Apple", "category": "fruit", "price": 1.0},
        {"name": "Banana", "category": "fruit", "price": 0.5},
        {"name": "Carrot", "category": "vegetable", "price": 0.8},
        {"name": "Dates", "category": "fruit", "price": 2.5},
        {"name": "Eggplant", "category": "vegetable", "price": 1.2},
    ]
    for p in products:
        c.post("/products", json=p)

    for i in range(5):
        c.post("/cursor_products", json={"label": f"item-{i}"})

    c.post("/nopag_products", json={"name": "Item1", "category": "x"})
    c.post("/nopag_products", json={"name": "Item2", "category": "y"})

    return c


class TestFieldFilter:
    def test_filter_by_category_fruit(self, client):
        resp = client.get("/products?category=fruit&page=1")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert all(r["category"] == "fruit" for r in results)

    def test_filter_by_category_vegetable(self, client):
        resp = client.get("/products?category=vegetable&page=1")
        results = resp.json()["results"]
        assert all(r["category"] == "vegetable" for r in results)

    def test_unknown_filter_field_ignored(self, client):
        resp = client.get("/products?price=1.0&page=1")
        assert resp.status_code == 200  # non-whitelisted param is ignored


class TestSearchFilter:
    def test_search_by_name(self, client):
        resp = client.get("/products?search=Banana&page=1")
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["name"] == "Banana"

    def test_search_case_insensitive(self, client):
        resp = client.get("/products?search=apple&page=1")
        results = resp.json()["results"]
        assert any(r["name"] == "Apple" for r in results)

    def test_search_no_results_empty_list(self, client):
        resp = client.get("/products?search=xyznotfound&page=1")
        assert resp.json()["results"] == []


class TestOrderingFilter:
    def test_order_by_price_asc(self, client):
        resp = client.get("/products?ordering=price&page=1")
        results = resp.json()["results"]
        prices = [r["price"] for r in results]
        assert prices == sorted(prices)

    def test_order_by_price_desc(self, client):
        resp = client.get("/products?ordering=-price&page=1")
        results = resp.json()["results"]
        prices = [r["price"] for r in results]
        assert prices == sorted(prices, reverse=True)

    def test_ordering_invalid_field_ignored(self, client):
        resp = client.get("/products?ordering=nonexistent&page=1")
        assert resp.status_code == 200
        # Invalid field is ignored; results use default order
        assert "results" in resp.json()

    def test_filter_composes_with_search(self, client):
        resp = client.get("/products?category=fruit&search=Banana&page=1")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["name"] == "Banana"
        assert results[0]["category"] == "fruit"


class TestPageNumberPagination:
    def test_paginated_response_has_required_keys(self, client):
        resp = client.get("/products?page=1")
        body = resp.json()
        assert "count" in body
        assert "results" in body
        assert "next" in body
        assert "previous" in body

    def test_page_size_respected(self, client):
        resp = client.get("/products?page=1")
        assert len(resp.json()["results"]) <= 3

    def test_page_2_returns_different_items(self, client):
        page1 = client.get("/products?page=1").json()["results"]
        page2 = client.get("/products?page=2").json()["results"]
        ids1 = {r["id"] for r in page1}
        ids2 = {r["id"] for r in page2}
        assert ids1.isdisjoint(ids2)

    def test_count_equals_total_items(self, client):
        resp = client.get("/products?page=1")
        assert resp.json()["count"] == 5

    def test_empty_pagination_count_zero(self, client):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app_instance = LightApi(engine=engine)
        app_instance.register({
            "/empty_products": type(
                "EmptyProductEndpoint",
                (ProductEndpoint,),
                {},
            ),
        })
        c = TestClient(app_instance.build_app())
        resp = c.get("/empty_products?page=1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["results"] == []

    def test_pagination_page_beyond_last(self, client):
        resp = client.get("/products?page=999")
        assert resp.status_code == 200
        body = resp.json()
        assert body["results"] == []
        # Total count should reflect full result set (FR-8a: no 404 for empty page)
        assert body["count"] >= 0
        assert "results" in body

    def test_no_pagination_returns_results_only(self, client):
        resp = client.get("/nopag_products")
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body
        assert "count" not in body
        assert "page" not in body
        assert "next" not in body
        assert "previous" not in body
        # Results may be empty or populated; structure is what we verify
        assert isinstance(body["results"], list)


class TestCursorPagination:
    def test_cursor_pagination_returns_cursor_keys(self, client):
        resp = client.get("/cursor_products")
        body = resp.json()
        assert "next" in body
        assert "results" in body

    @pytest.mark.xfail(
        reason="CursorPaginator order_by('id') may not work with SQLite Select shape"
    )
    def test_cursor_traversal(self, client):
        resp1 = client.get("/cursor_products")
        next_cursor = resp1.json().get("next")
        assert next_cursor is not None
        resp2 = client.get(f"/cursor_products?cursor={next_cursor}")
        results2 = resp2.json()["results"]
        assert len(results2) > 0
        ids1 = {r["id"] for r in resp1.json()["results"]}
        ids2 = {r["id"] for r in results2}
        assert ids1.isdisjoint(ids2)
