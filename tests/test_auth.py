import pytest
import time
from unittest.mock import MagicMock
import jwt
from lightapi.auth import JWTAuthentication


class TestJWTAuthentication:
    def test_authenticate_valid_token(self):
        auth = JWTAuthentication()

        # Create a valid token
        payload = {"user_id": 1, "exp": time.time() + 3600}
        token = jwt.encode(payload, auth.secret_key, algorithm=auth.algorithm)

        # Create mock request with token and state attribute
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        mock_request.state = MagicMock()

        result = auth.authenticate(mock_request)

        assert result is True
        assert hasattr(mock_request.state, 'user')
        assert mock_request.state.user['user_id'] == 1

    def test_authenticate_invalid_token(self):
        auth = JWTAuthentication()

        # Create an invalid token
        invalid_token = "invalid.token.string"

        # Create mock request with invalid token
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": f"Bearer {invalid_token}"}

        result = auth.authenticate(mock_request)

        assert result is False

    def test_authenticate_expired_token(self):
        auth = JWTAuthentication()

        # Create an expired token
        payload = {"user_id": 1, "exp": time.time() - 3600}  # 1 hour in the past
        token = jwt.encode(payload, auth.secret_key, algorithm=auth.algorithm)

        # Create mock request with expired token
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": f"Bearer {token}"}

        result = auth.authenticate(mock_request)

        assert result is False

    def test_authenticate_no_token(self):
        auth = JWTAuthentication()

        # Create mock request without token
        mock_request = MagicMock()
        mock_request.headers = {}

        result = auth.authenticate(mock_request)

        assert result is False

    def test_generate_token(self):
        auth = JWTAuthentication()

        user_data = {"user_id": 1, "username": "testuser"}
        token = auth.generate_token(user_data)

        # Decode the token and verify its contents
        decoded = jwt.decode(token, auth.secret_key, algorithms=[auth.algorithm])

        assert decoded["user_id"] == 1
        assert decoded["username"] == "testuser"
        assert "exp" in decoded
