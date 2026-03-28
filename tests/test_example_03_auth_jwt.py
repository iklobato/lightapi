"""Tests for example 03_auth_jwt.py - JWT Authentication flows."""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

os.environ.setdefault("LIGHTAPI_JWT_SECRET", "test-secret-key")

from lightapi import (
    LightApi,
    RestEndpoint,
    Field,
    HttpMethod,
    Serializer,
    Authentication,
    JWTAuthentication,
    IsAuthenticated,
)


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Protected book endpoint."""

    title: str = Field(min_length=1)

    class Meta:
        serializer = Serializer(read=["id", "title"])
        authentication = Authentication(
            backend=JWTAuthentication, permission=IsAuthenticated
        )


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(
        engine=engine,
        login_validator=lambda u, p: {"sub": "1", "username": u}
        if u == "admin" and p == "secret"
        else None,
        use_test_isolation=True,
    )
    app.register({"/books": BookEndpoint})
    with TestClient(app.build_app()) as client:
        yield client


def test_login_valid_credentials(client):
    """Test login with valid credentials returns token."""
    response = client.post(
        "/auth/login", json={"username": "admin", "password": "secret"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "user" in data
    assert data["user"]["username"] == "admin"


def test_login_invalid_credentials(client):
    """Test login with invalid credentials returns 401."""
    response = client.post(
        "/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401


def test_login_missing_credentials(client):
    """Test login with missing credentials returns 422."""
    response = client.post("/auth/login", json={})
    assert response.status_code == 422


def test_protected_endpoint_without_token(client):
    """Test accessing protected endpoint without token returns 401."""
    response = client.get("/books")
    assert response.status_code == 401


def test_protected_endpoint_with_invalid_token(client):
    """Test accessing protected endpoint with invalid token returns 401."""
    response = client.get("/books", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


def test_protected_endpoint_with_valid_token(client):
    """Test accessing protected endpoint with valid token succeeds."""
    # First login to get token
    login_response = client.post(
        "/auth/login", json={"username": "admin", "password": "secret"}
    )
    token = login_response.json()["token"]

    # Access protected endpoint
    response = client.get("/books", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_token_endpoint(client):
    """Test /auth/token endpoint also works."""
    # Use /auth/token instead of /auth/login
    response = client.post(
        "/auth/token", json={"username": "admin", "password": "secret"}
    )
    assert response.status_code == 200
    assert "token" in response.json()


def test_jwt_payload_contains_expected_claims(client):
    """Test JWT token payload structure."""
    import jwt

    login_response = client.post(
        "/auth/login", json={"username": "admin", "password": "secret"}
    )
    token = login_response.json()["token"]

    # Decode token without verification to check payload
    payload = jwt.decode(token, options={"verify_signature": False})
    assert "sub" in payload
    assert "username" in payload
    assert "exp" in payload  # Expiration


def test_create_book_with_auth(client):
    """Test creating a book with valid JWT."""
    # Login
    login_response = client.post(
        "/auth/login", json={"username": "admin", "password": "secret"}
    )
    token = login_response.json()["token"]

    # Create book
    response = client.post(
        "/books",
        json={"title": "New Book"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Book"


def test_create_book_without_auth(client):
    """Test creating a book without auth returns 401."""
    response = client.post("/books", json={"title": "New Book"})
    assert response.status_code == 401
