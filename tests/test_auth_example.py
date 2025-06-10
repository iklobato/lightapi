import os
from datetime import datetime, timedelta

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from examples.auth_example import (
    AuthEndpoint,
    CustomJWTAuth,
    PublicResource,
    SecretResource,
    UserProfile,
)
from lightapi.config import config

# Set environment variables for testing
os.environ["LIGHTAPI_JWT_SECRET"] = "test_secret_key_for_testing"
os.environ["LIGHTAPI_ENV"] = "test"

# Test secret key
TEST_SECRET_KEY = "test_secret_key_for_testing"


@pytest.fixture(autouse=True)
def setup_jwt_config():
    """Configure JWT secret for all tests."""
    # Set environment variable
    os.environ["LIGHTAPI_JWT_SECRET"] = TEST_SECRET_KEY
    # Update config directly
    config.update(jwt_secret=TEST_SECRET_KEY)
    yield
    # Clean up
    if "LIGHTAPI_JWT_SECRET" in os.environ:
        del os.environ["LIGHTAPI_JWT_SECRET"]


class TestCustomJWTAuth:
    """Test suite for the CustomJWTAuth class from auth_example.py.

    This class tests the JWT authentication implementation, including token
    verification and user information extraction from tokens.
    """

    def test_authenticate_valid_token(self):
        """Test that authenticate accepts a valid JWT token."""
        # Create a valid token
        payload = {
            "sub": "user_123",
            "username": "testuser",
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, TEST_SECRET_KEY, algorithm="HS256")

        # Create a mock request with the token
        class MockRequest:
            headers = {"Authorization": f"Bearer {token}"}
            method = "GET"

            def __init__(self):
                self.state = type("state", (), {})

        # Create the auth instance and test authentication
        auth = CustomJWTAuth()
        result = auth.authenticate(MockRequest())

        # Verify authentication succeeds
        assert result is True

        # Verify user info is stored in the request
        mock_request = MockRequest()
        auth.authenticate(mock_request)
        assert hasattr(mock_request.state, "user")
        assert mock_request.state.user["username"] == "testuser"
        assert mock_request.state.user["role"] == "admin"

    def test_authenticate_missing_token(self):
        """Test that authenticate rejects requests with missing tokens."""

        # Create a mock request without a token
        class MockRequest:
            headers = {}
            method = "GET"

        # Create the auth instance and test authentication
        auth = CustomJWTAuth()
        result = auth.authenticate(MockRequest())

        # Verify authentication fails
        assert result is False

    def test_authenticate_invalid_token(self):
        """Test that authenticate rejects invalid tokens."""

        # Create a mock request with an invalid token
        class MockRequest:
            headers = {"Authorization": "Bearer invalid.token.here"}
            method = "GET"

        # Create the auth instance and test authentication
        auth = CustomJWTAuth()
        result = auth.authenticate(MockRequest())

        # Verify authentication fails
        assert result is False

    def test_authenticate_expired_token(self):
        """Test that authenticate rejects expired tokens."""
        # Create an expired token
        payload = {
            "sub": "user_123",
            "username": "testuser",
            "role": "admin",
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
        }
        token = jwt.encode(payload, TEST_SECRET_KEY, algorithm="HS256")

        # Create a mock request with the expired token
        class MockRequest:
            headers = {"Authorization": f"Bearer {token}"}
            method = "GET"

        # Create the auth instance and test authentication
        auth = CustomJWTAuth()
        result = auth.authenticate(MockRequest())

        # Verify authentication fails
        assert result is False


class TestAuthEndpoint:
    """Test suite for the AuthEndpoint class from auth_example.py.

    This class tests the login functionality and token generation.
    """

    def test_post_valid_credentials(self):
        """Test that post generates a token for valid credentials."""

        # Create a mock request with valid credentials
        class MockRequest:
            data = {"username": "admin", "password": "password"}

        # Create the endpoint instance
        auth_endpoint = AuthEndpoint()

        # Call the post method
        response, status_code = auth_endpoint.post(MockRequest())

        # Verify the response
        assert status_code == 200
        assert "token" in response

        # Verify the token is valid
        token = response["token"]
        decoded = jwt.decode(token, TEST_SECRET_KEY, algorithms=["HS256"])
        assert decoded["username"] == "admin"
        assert decoded["role"] == "admin"

    def test_post_invalid_credentials(self):
        """Test that post rejects invalid credentials."""

        # Create a mock request with invalid credentials
        class MockRequest:
            data = {"username": "admin", "password": "wrong_password"}

        # Create the endpoint instance
        auth_endpoint = AuthEndpoint()

        # Call the post method
        response = auth_endpoint.post(MockRequest())

        # Verify the response
        assert response.status_code == 401
        assert "error" in response.body
        assert response.body["error"] == "Invalid credentials"


class TestProtectedResource:
    """Test suite for protected resources in auth_example.py.

    This class tests the SecretResource and UserProfile classes that require
    authentication before accessing their endpoints.
    """

    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database session for testing.

        Returns:
            Session: A SQLAlchemy session connected to an in-memory database.
        """
        engine = create_engine("sqlite:///:memory:")
        UserProfile.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()

    def test_secret_resource_with_valid_token(self):
        """Test that SecretResource returns data when authenticated."""
        # Create a valid token with user info
        payload = {
            "sub": "user_123",
            "username": "testuser",
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }

        # Create a mock request with the user info already extracted
        class MockRequest:
            def __init__(self):
                self.state = type("state", (), {})
                self.state.user = payload

        # Create the resource instance
        resource = SecretResource()

        # Call the get method
        response, status_code = resource.get(MockRequest())

        # Verify the response
        assert status_code == 200
        assert response["message"] == "Hello, testuser! You have admin access."

    def test_public_resource(self):
        """Test that PublicResource returns data without authentication."""

        # Create a mock request
        class MockRequest:
            pass

        # Create the resource instance
        resource = PublicResource()

        # Call the get method
        response, status_code = resource.get(MockRequest())

        # Verify the response
        assert status_code == 200
        assert response["message"] == "This is public information"

    def test_user_profile_get(self, db_session):
        """Test that UserProfile.get returns the user's profile.

        Args:
            db_session: The SQLAlchemy session fixture.
        """
        # Add a test profile to the database
        profile = UserProfile(
            user_id="user_123", full_name="Test User", email="test@example.com"
        )
        db_session.add(profile)
        db_session.commit()

        # Create a mock request with user info
        class MockRequest:
            def __init__(self):
                self.state = type("state", (), {})
                self.state.user = {"sub": "user_123"}

        # Create the profile instance and set up its environment
        user_profile = UserProfile()
        user_profile.session = db_session
        user_profile.auth = CustomJWTAuth()

        # Call the get method
        response, status_code = user_profile.get(MockRequest())

        # Verify the response
        assert status_code == 200
        assert response["user_id"] == "user_123"
        assert response["full_name"] == "Test User"
        assert response["email"] == "test@example.com"

    def test_user_profile_get_not_found(self, db_session):
        """Test that UserProfile.get returns 404 when profile not found.

        Args:
            db_session: The SQLAlchemy session fixture.
        """

        # Create a mock request with user info for non-existent profile
        class MockRequest:
            def __init__(self):
                self.state = type("state", (), {})
                self.state.user = {"sub": "non_existent_user"}

        # Create the profile instance and set up its environment
        user_profile = UserProfile()
        user_profile.session = db_session
        user_profile.auth = CustomJWTAuth()

        # Call the get method
        response = user_profile.get(MockRequest())

        # Verify the response
        assert response.status_code == 404
        assert response.body["error"] == "Profile not found"
