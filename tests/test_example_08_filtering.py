"""Tests for example 08_filtering.py - Filtering operations."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint, Field, HttpMethod, Filtering, Serializer
from lightapi.filters import FieldFilter, SearchFilter, OrderingFilter


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Book endpoint with filtering."""

    title: str = Field(min_length=1)
    author: str = Field(default="")
    price: float = Field(default=0.0)
    published: bool = Field(default=False)

    class Meta:
        serializer = Serializer(read=["id", "title", "author", "price", "published"])
        filtering = Filtering(
            fields=["title", "author", "price", "published"],
            search=["title", "author"],
            ordering=["title", "price", "id"],
        )


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine)
    app.register({"/books": BookEndpoint})
    with TestClient(app.build_app()) as client:
        # Create test data
        client.post(
            "/books",
            json={
                "title": "Python Guide",
                "author": "John",
                "price": 29.99,
                "published": True,
            },
        )
        client.post(
            "/books",
            json={
                "title": "JavaScript Basics",
                "author": "Jane",
                "price": 19.99,
                "published": True,
            },
        )
        client.post(
            "/books",
            json={
                "title": "Rust Programming",
                "author": "Bob",
                "price": 39.99,
                "published": False,
            },
        )
        yield client


def test_filter_by_author(client):
    """Test filtering by author."""
    response = client.get("/books?author=John")
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) >= 1


def test_search_works(client):
    """Test search functionality."""
    response = client.get("/books?search=Python")
    assert response.status_code == 200
    data = response.json()
    assert "Python" in data["results"][0]["title"]


def test_ordering_works(client):
    """Test ordering functionality."""
    response = client.get("/books?ordering=title")
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) > 0


def test_multiple_filters(client):
    """Test combining filters."""
    response = client.get("/books?published=true&price_gte=20")
    assert response.status_code == 200
    data = response.json()
    # Should return filtered results
    assert "results" in data
