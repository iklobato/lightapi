import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from examples.basic_rest_api import User


class TestUserEndpoint:
    """Test suite for the User endpoint in basic_rest_api.py.

    This class tests the basic REST functionality provided by the User model,
    including the default implementations of GET, POST, PUT, and DELETE methods.
    """

    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database session for testing.

        Returns:
            Session: A SQLAlchemy session connected to an in-memory database.
        """
        engine = create_engine("sqlite:///:memory:")
        User.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()

    def test_get_all_users(self, db_session):
        """Test that GET returns all users in the database.

        Args:
            db_session: The SQLAlchemy session fixture.
        """
        # Add some test users to the database
        user1 = User(name="John Doe", email="john@example.com", role="admin")
        user2 = User(name="Jane Smith", email="jane@example.com", role="user")
        db_session.add_all([user1, user2])
        db_session.commit()

        # Create a User instance and set up its environment
        user_endpoint = User()
        user_endpoint.session = db_session

        # Create a mock request
        class MockRequest:
            path_params = {}

        # Call the get method
        response, status_code = user_endpoint.get(MockRequest())

        # Assert the response contains the expected data
        assert status_code == 200
        assert "results" in response
        assert len(response["results"]) == 2

        # Verify users data
        users = response["results"]
        assert users[0]["name"] == "John Doe"
        assert users[0]["email"] == "john@example.com"
        assert users[0]["role"] == "admin"

        assert users[1]["name"] == "Jane Smith"
        assert users[1]["email"] == "jane@example.com"
        assert users[1]["role"] == "user"

    def test_get_user_by_id(self, db_session):
        """Test that GET with an ID parameter returns a specific user.

        Args:
            db_session: The SQLAlchemy session fixture.
        """
        # Add a test user to the database
        user = User(name="John Doe", email="john@example.com", role="admin")
        db_session.add(user)
        db_session.commit()

        # Create a User instance and set up its environment
        user_endpoint = User()
        user_endpoint.session = db_session

        # Create a mock request with path parameter
        class MockRequest:
            path_params = {"id": 1}

        # Call the get method
        response, status_code = user_endpoint.get(MockRequest())

        # Assert the response contains the expected data
        assert status_code == 200
        assert "results" in response
        assert len(response["results"]) == 1

        # Verify user data
        user_data = response["results"][0]
        assert user_data["id"] == 1
        assert user_data["name"] == "John Doe"
        assert user_data["email"] == "john@example.com"
        assert user_data["role"] == "admin"

    def test_post_user(self, db_session):
        """Test that POST creates a new user in the database.

        Args:
            db_session: The SQLAlchemy session fixture.
        """
        # Create a User instance and set up its environment
        user_endpoint = User()
        user_endpoint.session = db_session

        # Create a mock request with user data
        class MockRequest:
            data = {"name": "New User", "email": "new@example.com", "role": "editor"}

        # Call the post method
        response, status_code = user_endpoint.post(MockRequest())

        # Assert the response contains the expected data
        assert status_code == 201
        assert "result" in response

        # Verify response data
        user_data = response["result"]
        assert user_data["id"] == 1
        assert user_data["name"] == "New User"
        assert user_data["email"] == "new@example.com"
        assert user_data["role"] == "editor"

        # Verify that the user was actually saved to the database
        saved_user = db_session.query(User).first()
        assert saved_user is not None
        assert saved_user.name == "New User"
        assert saved_user.email == "new@example.com"
        assert saved_user.role == "editor"

    def test_put_user(self, db_session):
        """Test that PUT updates an existing user in the database.

        Args:
            db_session: The SQLAlchemy session fixture.
        """
        # Add a test user to the database
        user = User(name="Original Name", email="original@example.com", role="user")
        db_session.add(user)
        db_session.commit()

        # Create a User instance and set up its environment
        user_endpoint = User()
        user_endpoint.session = db_session

        # Create a mock request with updated data
        class MockRequest:
            path_params = {"id": 1}
            data = {
                "name": "Updated Name",
                "email": "updated@example.com",
                "role": "admin",
            }

        # Call the put method
        response, status_code = user_endpoint.put(MockRequest())

        # Assert the response contains the expected data
        assert status_code == 200
        assert "result" in response

        # Verify response data
        user_data = response["result"]
        assert user_data["id"] == 1
        assert user_data["name"] == "Updated Name"
        assert user_data["email"] == "updated@example.com"
        assert user_data["role"] == "admin"

        # Verify that the user was actually updated in the database
        updated_user = db_session.query(User).first()
        assert updated_user is not None
        assert updated_user.name == "Updated Name"
        assert updated_user.email == "updated@example.com"
        assert updated_user.role == "admin"

    def test_delete_user(self, db_session):
        """Test that DELETE removes a user from the database.

        Args:
            db_session: The SQLAlchemy session fixture.
        """
        # Add a test user to the database
        user = User(name="John Doe", email="john@example.com", role="admin")
        db_session.add(user)
        db_session.commit()

        # Create a User instance and set up its environment
        user_endpoint = User()
        user_endpoint.session = db_session

        # Create a mock request with path parameter
        class MockRequest:
            path_params = {"id": 1}

        # Call the delete method
        response, status_code = user_endpoint.delete(MockRequest())

        # Assert the response contains the expected data
        assert status_code == 204
        assert response["result"] == "Object deleted"

        # Verify that the user was actually deleted from the database
        user_count = db_session.query(User).count()
        assert user_count == 0

    def test_options(self, db_session):
        """Test that OPTIONS returns allowed HTTP methods.

        Args:
            db_session: The SQLAlchemy session fixture.
        """
        # Create a User instance and set up its environment
        user_endpoint = User()
        user_endpoint.session = db_session

        # Create a mock request
        class MockRequest:
            pass

        # Call the options method
        response, status_code = user_endpoint.options(MockRequest())

        # Assert the response contains the expected data
        assert status_code == 200
        assert "allowed_methods" in response
        # Compare sets instead of lists to make the test more robust to order changes
        assert set(response["allowed_methods"]) == set(
            ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        )
