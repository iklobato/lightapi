import time
from lightapi.auth import JWTAuthentication

def test_jwt_creation_and_verification():
    payload = {'user_id': 42, 'role': 'admin'}
    token = JWTAuthentication.generate_token(payload)
    decoded = JWTAuthentication.decode_token(token)
    
    assert decoded['user_id'] == 42
    assert decoded['role'] == 'admin'
    assert isinstance(decoded['exp'], float)

def test_expired_jwt_returns_none():
    token = JWTAuthentication.generate_token({'exp': time.time() - 10})
    assert JWTAuthentication.decode_token(token) is None

def test_invalid_jwt_returns_none():
    assert JWTAuthentication.decode_token('invalid.token.here') is None
