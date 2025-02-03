import os
import pytest
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

def pytest_addoption(parser):
    parser.addoption(
        "--db-url",
        action="store",
        default="sqlite:///:memory:",
        help="Database URL for testing"
    )

@pytest.fixture(scope="session")
def db_url(request):
    return request.config.getoption("--db-url")

@pytest.fixture(scope="session")
def db_engine(db_url):
    """Create a SQL Alchemy engine that's session-wide."""
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    yield engine
    engine.dispose()

@pytest.fixture(scope="session")
def Base():
    """Create a SQLAlchemy Base class for declarative models."""
    return declarative_base()

@pytest.fixture(scope="session")
def test_model(Base):
    """Create a test model class for use in tests."""
    class TestModel(Base):
        __tablename__ = 'test_models'
        id = Column(Integer, primary_key=True)
        name = Column(String(50), nullable=False)
        
        def __repr__(self):
            return f"<TestModel(id={self.id}, name='{self.name}')>"
    
    return TestModel

@pytest.fixture(scope="session")
def Session(db_engine):
    """Create a SQLAlchemy scoped session factory."""
    return scoped_session(sessionmaker(bind=db_engine))

@pytest.fixture(scope="function")
def db_session(Session, Base, db_engine):
    """Create a new database session for a test."""
    Base.metadata.create_all(db_engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(db_engine)
    Session.remove()

@pytest.fixture(scope="function")
def client():
    """Create a test client for the API."""
    from lightapi import LightApi
    app = LightApi()
    return app.test_client()

@pytest.fixture(scope="session")
def jwt_secret():
    """Provide a secret key for JWT testing."""
    return "test_secret_key"

@pytest.fixture(scope="function")
def auth_headers(jwt_secret):
    """Provide authentication headers for protected endpoints."""
    from lightapi.auth import JWTAuthentication
    token = JWTAuthentication.generate_token(
        {"user_id": 1, "role": "admin"},
        secret=jwt_secret
    )
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def sample_data(db_session, test_model):
    """Create sample data for tests."""
    items = [
        test_model(name=f"Test Item {i}")
        for i in range(1, 6)
    ]
    db_session.bulk_save_objects(items)
    db_session.commit()
    return items
