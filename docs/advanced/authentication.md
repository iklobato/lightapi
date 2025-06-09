---
title: Enterprise Authentication & Security
description: Comprehensive guide to authentication, authorization, and security in LightAPI
---

# Enterprise Authentication & Security

LightAPI provides a robust, enterprise-grade authentication system designed for modern web applications. With built-in JWT support, CORS integration, and extensible authentication backends, LightAPI ensures your APIs are secure while maintaining ease of use.

## Overview

LightAPI's authentication system features:

- **🔐 JWT Authentication**: Industry-standard JWT tokens with automatic validation
- **🌐 CORS Integration**: Seamless CORS preflight request handling
- **🔑 Role-Based Access Control**: Advanced permission and role management
- **🛡️ Multi-Factor Authentication**: Support for MFA and advanced security
- **⚡ High Performance**: Minimal overhead with intelligent caching
- **🔧 Extensible**: Custom authentication backends for any requirement

## JWT Authentication

### Basic JWT Implementation

The `JWTAuthentication` class provides production-ready JWT authentication with intelligent defaults:

```python
from lightapi.rest import RestEndpoint
from lightapi.core import LightApi
from lightapi.auth import JWTAuthentication
import os

class SecureEndpoint(RestEndpoint):
    """Endpoint protected by JWT authentication"""
    __tablename__ = 'secure_data'
    
    class Configuration:
        authentication_class = JWTAuthentication
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    
    def get(self, request):
        """Access user information from validated token"""
        user = request.state.user  # Populated by authentication
        return {
            'message': f'Hello, {user.get("username", "User")}',
            'user_id': user.get('user_id'),
            'roles': user.get('roles', []),
            'permissions': user.get('permissions', [])
        }
    
    def post(self, request):
        """Create data with user context"""
        user = request.state.user
        data = request.json()
        
        # Add audit information
        data['created_by'] = user['user_id']
        data['created_at'] = datetime.utcnow().isoformat()
        
        return {'message': 'Data created', 'data': data}

# Configure application
app = LightApi()
app.register({'/secure': SecureEndpoint})

# Set JWT secret via environment variable (recommended)
os.environ['LIGHTAPI_JWT_SECRET'] = 'your-256-bit-secret-key-here'
```

### Token Generation and Management

```python
from lightapi.auth import JWTAuthentication
from datetime import datetime, timedelta

# Initialize JWT handler
jwt_auth = JWTAuthentication()

# Generate tokens with comprehensive payload
user_payload = {
    'user_id': 12345,
    'username': 'john.doe',
    'email': 'john.doe@company.com',
    'roles': ['user', 'premium'],
    'permissions': ['read', 'write', 'delete'],
    'department': 'engineering',
    'issued_at': datetime.utcnow().isoformat(),
    'session_id': 'sess_abc123'
}

# Generate token (default 1 hour expiration)
token = jwt_auth.generate_token(user_payload)

# Generate token with custom expiration
long_lived_token = jwt_auth.generate_token(
    user_payload, 
    expiration_delta=timedelta(days=30)  # 30-day token
)

# Validate and decode token
try:
    decoded_payload = jwt_auth.validate_token(token)
    print(f"Token valid for user: {decoded_payload['username']}")
except Exception as e:
    print(f"Token validation failed: {e}")
```

### CORS and Preflight Integration

LightAPI's JWT authentication automatically handles CORS preflight requests without compromising security:

```python
from lightapi.core import LightApi, CORSMiddleware
from lightapi.auth import JWTAuthentication
from lightapi.rest import RestEndpoint

class CORSAwareEndpoint(RestEndpoint):
    """Endpoint with automatic CORS preflight support"""
    
    class Configuration:
        authentication_class = JWTAuthentication
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']

app = LightApi(title="CORS-Enabled API")

# Configure CORS middleware
app.add_middleware([
    CORSMiddleware(
        allow_origins=['https://app.company.com', 'https://admin.company.com'],
        allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        allow_headers=['Authorization', 'Content-Type', 'X-Request-ID'],
        allow_credentials=True,
        expose_headers=['X-Process-Time'],
        max_age=86400  # 24-hour preflight cache
    )
])

app.register({'/api/data': CORSAwareEndpoint})

# Request flow:
# OPTIONS /api/data -> 200 OK (no authentication required)
# GET /api/data -> 403 Forbidden (without valid JWT)
# GET /api/data with Bearer token -> 200 OK (authenticated)
```

## Advanced JWT Configuration

### Enterprise JWT Authentication

```python
from lightapi.auth import JWTAuthentication
from datetime import timedelta
import redis
import json
import logging

logger = logging.getLogger(__name__)

class EnterpriseJWTAuth(JWTAuthentication):
    """Enterprise JWT authentication with advanced features"""
    
    def __init__(self):
        super().__init__(
            secret_key=os.getenv('JWT_SECRET_KEY'),
            algorithm='HS256',
            token_expiry=timedelta(hours=8),  # 8-hour work session
            refresh_threshold=timedelta(minutes=30)  # Refresh when < 30 min left
        )
        
        # Redis for token blacklisting and session management
        self.redis_client = redis.Redis.from_url(
            os.getenv('REDIS_URL', 'redis://localhost:6379/1')
        )
    
    def validate_token(self, token):
        """Enhanced token validation with blacklist check"""
        # Check if token is blacklisted
        if self.redis_client.exists(f"blacklist:{token}"):
            raise AuthenticationError("Token has been revoked")
        
        # Standard validation
        payload = super().validate_token(token)
        
        # Load fresh user permissions
        user_permissions = self.load_user_permissions(payload['user_id'])
        payload['permissions'] = user_permissions
        
        # Check for account suspension
        if self.is_user_suspended(payload['user_id']):
            raise AuthenticationError("User account is suspended")
        
        return payload
    
    def blacklist_token(self, token, reason="logout"):
        """Add token to blacklist"""
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            expiry = payload.get('exp', 0)
            ttl = max(0, expiry - int(time.time()))
            
            self.redis_client.setex(
                f"blacklist:{token}",
                ttl,
                json.dumps({
                    'reason': reason,
                    'blacklisted_at': datetime.utcnow().isoformat()
                })
            )
        except Exception as e:
            logger.warning(f"Failed to blacklist token: {e}")
    
    def load_user_permissions(self, user_id):
        """Load current user permissions from database"""
        # Implementation depends on your user management system
        # This is a placeholder for demonstration
        user_permissions = self.redis_client.get(f"user_permissions:{user_id}")
        if user_permissions:
            return json.loads(user_permissions)
        
        # Fallback to database query
        return self.query_user_permissions_from_db(user_id)
    
    def is_user_suspended(self, user_id):
        """Check if user account is suspended"""
        status = self.redis_client.get(f"user_status:{user_id}")
        return status == b'suspended'
    
    def get_auth_error_response(self, request):
        """Custom error response with security headers"""
        return JSONResponse(
            {
                "error": "Authentication required",
                "code": "AUTH_REQUIRED",
                "timestamp": datetime.utcnow().isoformat()
            },
            status_code=403,
            headers={
                "WWW-Authenticate": "Bearer",
                "X-Auth-Required": "true"
            }
        )
```

### Multi-Factor Authentication Integration

```python
from lightapi.auth import JWTAuthentication
import pyotp
import qrcode
import io
import base64

class MFAJWTAuthentication(JWTAuthentication):
    """JWT Authentication with MFA support"""
    
    def validate_token(self, token):
        """Validate token and check MFA requirements"""
        payload = super().validate_token(token)
        
        # Check if MFA is required for this user/action
        if self.requires_mfa(payload, request):
            if not payload.get('mfa_verified', False):
                raise MFARequiredError("Multi-factor authentication required")
        
        return payload
    
    def requires_mfa(self, user_payload, request):
        """Determine if MFA is required"""
        # MFA required for admin operations
        if 'admin' in user_payload.get('roles', []):
            return True
        
        # MFA required for sensitive endpoints
        sensitive_paths = ['/admin', '/users', '/payments']
        if any(request.url.path.startswith(path) for path in sensitive_paths):
            return True
        
        # MFA required for write operations on weekends
        if request.method in ['POST', 'PUT', 'DELETE'] and datetime.now().weekday() >= 5:
            return True
        
        return False
    
    def generate_mfa_token(self, user_payload, mfa_code):
        """Generate token after MFA verification"""
        # Verify TOTP code
        user_secret = self.get_user_mfa_secret(user_payload['user_id'])
        totp = pyotp.TOTP(user_secret)
        
        if not totp.verify(mfa_code, window=1):  # Allow 30-second window
            raise AuthenticationError("Invalid MFA code")
        
        # Add MFA verification to payload
        enhanced_payload = {
            **user_payload,
            'mfa_verified': True,
            'mfa_verified_at': datetime.utcnow().isoformat(),
            'mfa_method': 'totp'
        }
        
        return self.generate_token(enhanced_payload)
    
    def setup_mfa_for_user(self, user_id, user_email):
        """Setup MFA for a user and return QR code"""
        secret = pyotp.random_base32()
        
        # Store secret securely (encrypted in database)
        self.store_user_mfa_secret(user_id, secret)
        
        # Generate QR code for authenticator app
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user_email,
            issuer_name="Your Company API"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_code_data = base64.b64encode(buffer.getvalue()).decode()
        
        return {
            'secret': secret,
            'qr_code': f"data:image/png;base64,{qr_code_data}",
            'manual_entry_key': secret
        }

class MFARequiredError(Exception):
    """Exception raised when MFA is required"""
    pass

# Usage in endpoint
class SecureAdminEndpoint(RestEndpoint):
    class Configuration:
        authentication_class = MFAJWTAuthentication
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
    
    def handle_mfa_required(self, request, exception):
        """Handle MFA requirement"""
        return JSONResponse(
            {
                "error": "Multi-factor authentication required",
                "mfa_required": True,
                "setup_url": "/auth/mfa/setup"
            },
            status_code=403
        )
```

## Role-Based Access Control (RBAC)

### Advanced Permission System

```python
from lightapi.auth import JWTAuthentication
from lightapi.rest import RestEndpoint
from functools import wraps

class RBACJWTAuthentication(JWTAuthentication):
    """JWT Authentication with role-based access control"""
    
    def authorize_endpoint(self, request, required_permissions=None, required_roles=None):
        """Check if user has required permissions/roles"""
        user = request.state.user
        
        # Check roles
        if required_roles:
            user_roles = set(user.get('roles', []))
            if not user_roles.intersection(set(required_roles)):
                raise PermissionError(f"Required roles: {required_roles}")
        
        # Check permissions
        if required_permissions:
            user_permissions = set(user.get('permissions', []))
            if not user_permissions.intersection(set(required_permissions)):
                raise PermissionError(f"Required permissions: {required_permissions}")
        
        return True

def require_permissions(*permissions):
    """Decorator for method-level permission checking"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if hasattr(self, 'Configuration') and hasattr(self.Configuration, 'authentication_class'):
                auth = self.Configuration.authentication_class()
                auth.authorize_endpoint(request, required_permissions=permissions)
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator

def require_roles(*roles):
    """Decorator for method-level role checking"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if hasattr(self, 'Configuration') and hasattr(self.Configuration, 'authentication_class'):
                auth = self.Configuration.authentication_class()
                auth.authorize_endpoint(request, required_roles=roles)
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator

class AdminEndpoint(RestEndpoint):
    """Admin-only endpoint with granular permissions"""
    __tablename__ = 'admin_data'
    
    class Configuration:
        authentication_class = RBACJWTAuthentication
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
    
    @require_roles('admin', 'super_admin')
    def get(self, request):
        """List data - requires admin role"""
        return {'data': 'admin data'}
    
    @require_permissions('admin.create', 'data.write')
    def post(self, request):
        """Create data - requires specific permissions"""
        return {'message': 'Data created'}
    
    @require_roles('super_admin')
    @require_permissions('admin.delete')
    def delete(self, request, pk):
        """Delete data - requires both role and permission"""
        return {'message': f'Deleted item {pk}'}
```

## Custom Authentication Backends

### API Key Authentication

```python
from lightapi.auth import BaseAuthentication
from starlette.responses import JSONResponse
import hashlib
import hmac
import time

class APIKeyAuthentication(BaseAuthentication):
    """API Key authentication with rate limiting and rotation"""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(os.getenv('REDIS_URL'))
    
    def authenticate(self, request):
        """Validate API key from headers"""
        # Skip OPTIONS requests for CORS
        if request.method == 'OPTIONS':
            return True
        
        # Extract API key
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return False
        
        # Validate key format
        if not self.is_valid_key_format(api_key):
            return False
        
        # Check against active keys
        key_info = self.validate_api_key(api_key)
        if not key_info:
            return False
        
        # Rate limiting check
        if not self.check_rate_limit(api_key, key_info):
            return False
        
        # Populate request state
        request.state.user = {
            'api_key': api_key,
            'client_id': key_info['client_id'],
            'permissions': key_info['permissions'],
            'rate_limit': key_info['rate_limit'],
            'auth_method': 'api_key'
        }
        
        # Log usage
        self.log_api_key_usage(api_key, request)
        
        return True
    
    def is_valid_key_format(self, api_key):
        """Validate API key format"""
        # Example: ak_live_1234567890abcdef (prefix_env_random)
        parts = api_key.split('_')
        return (
            len(parts) >= 3 and
            parts[0] == 'ak' and
            parts[1] in ['live', 'test'] and
            len(parts[2]) >= 16
        )
    
    def validate_api_key(self, api_key):
        """Validate API key against database/cache"""
        # Check Redis cache first
        cached_info = self.redis_client.get(f"api_key:{api_key}")
        if cached_info:
            return json.loads(cached_info)
        
        # Query database
        key_info = self.query_api_key_from_db(api_key)
        if key_info and key_info['is_active']:
            # Cache for 5 minutes
            self.redis_client.setex(
                f"api_key:{api_key}",
                300,
                json.dumps(key_info)
            )
            return key_info
        
        return None
    
    def check_rate_limit(self, api_key, key_info):
        """Implement rate limiting per API key"""
        rate_limit = key_info.get('rate_limit', 1000)  # Default 1000/hour
        window = 3600  # 1 hour window
        
        current_window = int(time.time() // window)
        key = f"rate_limit:{api_key}:{current_window}"
        
        current_usage = self.redis_client.get(key)
        if current_usage and int(current_usage) >= rate_limit:
            return False
        
        # Increment usage
        pipe = self.redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        pipe.execute()
        
        return True
    
    def get_auth_error_response(self, request):
        """Custom error response for API key auth"""
        return JSONResponse(
            {
                "error": "Invalid or missing API key",
                "code": "INVALID_API_KEY",
                "docs": "https://docs.company.com/api/authentication"
            },
            status_code=401,
            headers={"WWW-Authenticate": "ApiKey"}
        )

# Usage
class APIEndpoint(RestEndpoint):
    class Configuration:
        authentication_class = APIKeyAuthentication
        http_method_names = ['GET', 'POST']
```

### OAuth2 Integration

```python
from lightapi.auth import BaseAuthentication
import requests
from urllib.parse import urlencode

class OAuth2Authentication(BaseAuthentication):
    """OAuth2 bearer token authentication"""
    
    def __init__(self):
        self.oauth_server_url = os.getenv('OAUTH_SERVER_URL')
        self.client_id = os.getenv('OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('OAUTH_CLIENT_SECRET')
    
    def authenticate(self, request):
        """Validate OAuth2 bearer token"""
        if request.method == 'OPTIONS':
            return True
        
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return False
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Validate token with OAuth server
        user_info = self.validate_oauth_token(token)
        if not user_info:
            return False
        
        request.state.user = {
            'oauth_token': token,
            'user_id': user_info['sub'],
            'email': user_info['email'],
            'scopes': user_info['scope'].split(' '),
            'auth_method': 'oauth2'
        }
        
        return True
    
    def validate_oauth_token(self, token):
        """Validate token with OAuth2 server"""
        try:
            response = requests.post(
                f"{self.oauth_server_url}/oauth/token/info",
                headers={'Authorization': f'Bearer {token}'},
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        
        return None
```

## Global Authentication Middleware

### Centralized Authentication

```python
from lightapi.core import LightApi, AuthenticationMiddleware
from lightapi.auth import JWTAuthentication

# Create application with global authentication
app = LightApi(
    title="Secure Enterprise API",
    description="All endpoints require authentication"
)

# Configure global authentication middleware
app.add_middleware([
    AuthenticationMiddleware(
        JWTAuthentication,
        exclude_paths=[
            '/health',           # Health check endpoint
            '/metrics',          # Monitoring endpoint
            '/api/docs',         # API documentation
            '/auth/login',       # Login endpoint
            '/auth/register',    # Registration endpoint
            '/auth/forgot'       # Password reset
        ],
        include_patterns=[
            '/api/v1/*',         # All v1 API endpoints
            '/admin/*',          # All admin endpoints
        ]
    )
])

# All registered endpoints automatically inherit authentication
app.register({
    '/api/v1/users': UserEndpoint,
    '/api/v1/products': ProductEndpoint,
    '/admin/dashboard': AdminDashboard
})
```

## Security Best Practices

### Production Security Configuration

```python
import os
import secrets
from lightapi.core import LightApi
from lightapi.auth import JWTAuthentication

class ProductionJWTAuth(JWTAuthentication):
    """Production-hardened JWT authentication"""
    
    def __init__(self):
        # Use strong secret from environment
        secret_key = os.getenv('JWT_SECRET_KEY')
        if not secret_key or len(secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        
        super().__init__(
            secret_key=secret_key,
            algorithm='HS256',
            token_expiry=timedelta(minutes=15),  # Short-lived tokens
            refresh_threshold=timedelta(minutes=5)
        )
    
    def generate_token(self, payload, expiration_delta=None):
        """Enhanced token generation with security headers"""
        # Add security claims
        enhanced_payload = {
            **payload,
            'jti': secrets.token_urlsafe(16),  # JWT ID for revocation
            'iss': 'company-api',               # Issuer
            'aud': 'company-app',               # Audience
            'iat': datetime.utcnow(),           # Issued at
            'nbf': datetime.utcnow(),           # Not before
        }
        
        return super().generate_token(enhanced_payload, expiration_delta)

# Production application setup
app = LightApi(
    debug=False,  # Never enable debug in production
    title="Production API",
    cors_origins=os.getenv('ALLOWED_ORIGINS', '').split(',')
)

# Security headers middleware
class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        async def send_with_security_headers(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                
                # Add security headers
                security_headers = [
                    (b'x-content-type-options', b'nosniff'),
                    (b'x-frame-options', b'DENY'),
                    (b'x-xss-protection', b'1; mode=block'),
                    (b'strict-transport-security', b'max-age=31536000; includeSubDomains'),
                    (b'content-security-policy', b"default-src 'self'"),
                    (b'referrer-policy', b'strict-origin-when-cross-origin'),
                ]
                
                headers.extend(security_headers)
                message['headers'] = headers
            
            await send(message)
        
        await self.app(scope, receive, send_with_security_headers)

# Apply security middleware
app.add_middleware([SecurityHeadersMiddleware])
```

This comprehensive authentication system provides enterprise-grade security while maintaining the simplicity and performance that LightAPI is known for. The modular design allows you to implement exactly the authentication strategy your application needs, from simple API keys to complex multi-factor authentication systems.
