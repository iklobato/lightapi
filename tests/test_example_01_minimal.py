"""Tests for example 01_minimal.py - Full CRUD operations."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import Field, HttpMethod, LightApi, RestEndpoint, Serializer


class BookEndpoint(
    RestEndpoint,
    HttpMethod.GET,
    HttpMethod.POST,
    HttpMethod.PUT,
    HttpMethod.PATCH,
    HttpMethod.DELETE,
):
    """Book endpoint with title field."""

    title: str = Field(min_length=1)
    author: str = Field(default="Unknown")

    class Meta:
        serializer = Serializer(read=["id", "title", "author"])


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
        yield client


def test_create_book(client):
    """Test creating a book via POST."""
    response = client.post("/books", json={"title": "Test Book", "author": "John Doe"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Book"
    assert data["author"] == "John Doe"
    assert "id" in data


def test_create_book_without_author(client):
    """Test creating a book with default author."""
    response = client.post("/books", json={"title": "Default Author Book"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Default Author Book"
    assert data["author"] == "Unknown"


def test_create_book_validation_error(client):
    """Test creating a book without required field."""
    response = client.post("/books", json={"author": "No Title"})
    assert response.status_code == 422


def test_list_books(client):
    """Test listing books."""
    # Create a book first
    client.post("/books", json={"title": "Book 1", "author": "Author 1"})

    response = client.get("/books")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["title"] == "Book 1"


def test_get_book_detail(client):
    """Test getting a single book."""
    # Create a book
    create_response = client.post(
        "/books", json={"title": "Detail Book", "author": "Author"}
    )
    book_id = create_response.json()["id"]

    response = client.get(f"/books/{book_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Detail Book"


def test_get_book_not_found(client):
    """Test getting non-existent book."""
    response = client.get("/books/9999")
    assert response.status_code == 404


def test_update_book(client):
    """Test updating a book."""
    # Create a book
    create_response = client.post(
        "/books", json={"title": "Original Title", "author": "Original"}
    )
    book = create_response.json()
    book_id = book["id"]

    # Update with version
    response = client.put(
        f"/books/{book_id}",
        json={
            "title": "Updated Title",
            "author": "Updated",
            "version": book["version"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"


def test_patch_book(client):
    """Test partial update of a book."""
    # Create a book
    create_response = client.post(
        "/books", json={"title": "Original", "author": "Original"}
    )
    book = create_response.json()
    book_id = book["id"]

    # Patch with version
    response = client.patch(
        f"/books/{book_id}", json={"title": "Patched", "version": book["version"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Patched"
    assert data["author"] == "Original"  # Unchanged


def test_delete_book(client):
    """Test deleting a book."""
    # Create a book
    create_response = client.post(
        "/books", json={"title": "To Delete", "author": "Author"}
    )
    book = create_response.json()
    book_id = book["id"]

    # Delete with version
    response = client.delete(f"/books/{book_id}?version={book['version']}")
    assert response.status_code == 204

    # Verify deleted
    get_response = client.get(f"/books/{book_id}")
    assert get_response.status_code == 404


def test_crud_full_flow(client):
    """Test complete CRUD flow."""
    # Create
    create_response = client.post(
        "/books", json={"title": "CRUD Test", "author": "Author"}
    )
    assert create_response.status_code == 201
    book = create_response.json()
    book_id = book["id"]

    # Read
    get_response = client.get(f"/books/{book_id}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "CRUD Test"

    # Update with version (optimistic locking)
    update_response = client.put(
        f"/books/{book_id}",
        json={
            "title": "Updated Title",
            "author": "New Author",
            "version": book["version"],
        },
    )
    assert update_response.status_code == 200

    # Verify update
    verify_response = client.get(f"/books/{book_id}")
    assert verify_response.json()["title"] == "Updated Title"

    # Delete
    delete_response = client.delete(f"/books/{book_id}")
    assert delete_response.status_code == 204

    # Verify deleted
    not_found_response = client.get(f"/books/{book_id}")
    assert not_found_response.status_code == 404


def test_list_empty(client):
    """Test listing books when none exist."""
    response = client.get("/books")
    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []
