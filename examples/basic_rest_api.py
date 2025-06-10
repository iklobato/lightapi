from sqlalchemy import Column, Integer, String

from lightapi.core import LightApi
from lightapi.models import Base, register_model_class
from lightapi.rest import RestEndpoint


# Define a model that inherits from RestEndpoint
@register_model_class
class User(RestEndpoint):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    role = Column(String(50))

    # The default implementation already includes:
    # - GET: List all users or get a specific user by ID
    # - POST: Create a new user
    # - PUT: Update an existing user
    # - DELETE: Delete a user
    # - OPTIONS: Return allowed methods


if __name__ == "__main__":
    # Initialize the API with SQLite database
    app = LightApi(
        database_url="sqlite:///basic_example.db",
        swagger_title="Basic REST API Example",
        swagger_version="1.0.0",
        swagger_description="Simple REST API demonstrating basic CRUD operations",
    )

    # Register our endpoint
    app.register({"/users": User})

    print("Server running at http://localhost:8000")
    print("API documentation available at http://localhost:8000/docs")

    # Run the server
    app.run(host="localhost", port=8000, debug=True)
