import datetime
import json

import jwt
from sqlalchemy import Column, Integer, String

from lightapi.auth import JWTAuthentication
from lightapi.config import config
from lightapi.core import LightApi, Middleware, Response
from lightapi.models import Base, register_model_class
from lightapi.rest import RestEndpoint


# Custom authentication class
class CustomJWTAuth(JWTAuthentication):
    def __init__(self):
        super().__init__()
        self.secret_key = config.jwt_secret

    def authenticate(self, request):
        # Use the parent class implementation
        return super().authenticate(request)


# Login endpoint to get a token
class AuthEndpoint(RestEndpoint):
    __abstract__ = True  # Not a database model

    def post(self, request):
        data = getattr(request, "data", {})
        username = data.get("username")
        password = data.get("password")

        # Simple authentication (replace with database lookup in real apps)
        if username == "admin" and password == "password":
            # Create a JWT token
            payload = {
                "sub": "user_1",
                "username": username,
                "role": "admin",
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            }
            token = jwt.encode(payload, config.jwt_secret, algorithm="HS256")

            return {"token": token}, 200
        else:
            return Response({"error": "Invalid credentials"}, status_code=401)


# Protected resource that requires authentication
class SecretResource(RestEndpoint):
    __abstract__ = True  # Not a database model

    class Configuration:
        authentication_class = CustomJWTAuth

    def get(self, request):
        try:
            # Access the user info stored during authentication
            username = request.state.user.get("username")
            role = request.state.user.get("role")

            return {
                "message": f"Hello, {username}! You have {role} access.",
                "secret_data": "This is protected information",
            }, 200
        except Exception as e:
            import traceback

            print(f"Error in SecretResource.get: {e}")
            print(traceback.format_exc())
            return {"error": str(e)}, 500


# Public endpoint that doesn't require authentication
class PublicResource(RestEndpoint):
    __abstract__ = True  # Not a database model

    def get(self, request):
        try:
            return {"message": "This is public information"}, 200
        except Exception as e:
            import traceback

            print(f"Error in PublicResource.get: {e}")
            print(traceback.format_exc())
            return {"error": str(e)}, 500


# User profile endpoint that requires authentication
@register_model_class
class UserProfile(RestEndpoint):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(50))
    full_name = Column(String(100))
    email = Column(String(100))

    class Configuration:
        authentication_class = CustomJWTAuth

    # Override GET to return only the current user's profile
    def get(self, request):
        user_id = request.state.user.get("sub")
        profile = self.session.query(self.__class__).filter_by(user_id=user_id).first()

        if profile:
            return {
                "id": profile.id,
                "user_id": profile.user_id,
                "full_name": profile.full_name,
                "email": profile.email,
            }, 200
        else:
            return Response({"error": "Profile not found"}, status_code=404)


if __name__ == "__main__":
    app = LightApi(
        database_url="sqlite:///auth_example.db",
        swagger_title="Authentication Example",
        swagger_version="1.0.0",
        swagger_description="Example showing JWT authentication with LightAPI",
    )

    app.register(
        {
            "/auth/login": AuthEndpoint,
            "/public": PublicResource,
            "/secret": SecretResource,
            "/profile": UserProfile,
        }
    )

    print("Server running at http://localhost:8000")
    print("API documentation available at http://localhost:8000/docs")
    print("\nTo get a token:")
    print(
        'curl -X POST http://localhost:8000/auth/login -H \'Content-Type: application/json\' -d \'{"username": "admin", "password": "password"}\''
    )
    print("\nTo access protected resource:")
    print(
        "curl -X GET http://localhost:8000/secret -H 'Authorization: Bearer YOUR_TOKEN'"
    )

    app.run(host="localhost", port=8000, debug=True)
