"""Tests for example 06_pagination_page.py - Page number pagination."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import Field, HttpMethod, LightApi, Pagination, RestEndpoint, Serializer


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Book endpoint with pagination."""

    title: str = Field(min_length=1)

    class Meta:
        serializer = Serializer(read=["id", "title"])
        pagination = Pagination(style="page_number", page_size=3)


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine, use_test_isolation=True)
    app.register({"/books": BookEndpoint})
    with TestClient(app.build_app()) as client:
        # Create test data
        for i in range(10):
            client.post("/books", json={"title": f"Book {i}"})
        yield client


def test_list_returns_pagination(client):
    """Test that list returns pagination metadata."""
    response = client.get("/books")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "page" in data or "pages" in data


def test_list_returns_correct_page_size(client):
    """Test that page returns configured page size."""
    response = client.get("/books")
    data = response.json()
    # Should return at most page_size items
    assert len(data["results"]) <= 3


def test_pagination_page_param(client):
    """Test page parameter works."""
    response = client.get("/books?page=2")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 3
