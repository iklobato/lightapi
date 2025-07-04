import base64
from datetime import datetime

import sqlalchemy
import sqlalchemy.orm
from sqlalchemy import Boolean, Column, DateTime, Integer, String

from lightapi.database import Base


def setup_database(database_url: str = "sqlite:///app.db"):
    """
    Set up the database connection and create tables.

    Initializes SQLAlchemy with the provided database URL,
    creates the database tables, and returns the engine
    and session factory.

    Args:
        database_url: The SQLAlchemy database URL.

    Returns:
        tuple: A tuple containing (engine, Session).
    """
    engine = sqlalchemy.create_engine(database_url)

    try:
        Base.metadata.create_all(engine)
    except Exception:
        pass

    Session = sqlalchemy.orm.sessionmaker(bind=engine)
    return engine, Session


def register_model_class(cls):
    """
    Register a RestEndpoint class as a SQLAlchemy model.

    This function is used to make a RestEndpoint class work properly with SQLAlchemy.
    It ensures the metadata is correctly set up and the class is registered with the
    declarative base.

    Args:
        cls: The class to register as a SQLAlchemy model.

    Returns:
        The registered model class.
    """
    # Skip if it's not a proper model class with a tablename
    if not hasattr(cls, "__tablename__") or cls.__tablename__ is None:
        return cls

    # If the class is already a subclass of Base, just return it
    if issubclass(cls, Base):
        return cls

    # Create a unique class name by adding the module name as a prefix
    # This prevents conflicts between different classes with the same name
    unique_name = f"{cls.__module__}.{cls.__name__}"

    # Create a new class that inherits from both Base and the original class
    # Use extend_existing=True to handle multiple model definitions
    new_cls = type(
        unique_name,
        (Base, cls),
        {
            "__tablename__": cls.__tablename__,
            "__table_args__": {"extend_existing": True},
        },
    )

    return new_cls


class Person(Base):
    """
    Person model representing a user or individual.

    Attributes:
        id: Primary key.
        name: Person's name.
        email: Person's email address (unique).
        email_verified: Whether the email has been verified.
    """

    __tablename__ = "person"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    email = Column(String, unique=True)
    email_verified = Column(Boolean, default=False)

    def as_dict(self):
        """
        Convert the model instance to a dictionary.

        Returns:
            dict: Dictionary representation of the person.
        """
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "email_verified": self.email_verified,
        }

    def serialize(self):
        result = {}
        for col in self.__table__.columns:
            val = getattr(self, col.name)
            if isinstance(val, bytes):
                result[col.name] = base64.b64encode(val).decode()
            elif isinstance(val, (datetime, datetime.date)):
                result[col.name] = val.isoformat()
            else:
                result[col.name] = val
        return result


class Company(Base):
    """
    Company model representing a business organization.

    Attributes:
        id: Primary key.
        name: Company name.
        email: Company email address (unique).
        website: Company website URL.
    """

    __tablename__ = "company"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    email = Column(String, unique=True)
    website = Column(String)

    def as_dict(self):
        """
        Convert the model instance to a dictionary.

        Returns:
            dict: Dictionary representation of the company.
        """
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "website": self.website,
        }

    def serialize(self):
        result = {}
        for col in self.__table__.columns:
            val = getattr(self, col.name)
            if isinstance(val, bytes):
                result[col.name] = base64.b64encode(val).decode()
            elif isinstance(val, (datetime, datetime.date)):
                result[col.name] = val.isoformat()
            else:
                result[col.name] = val
        return result


class Post(Base):
    """
    Post model representing a blog post.

    Attributes:
        id: Primary key.
        title: Title of the post.
        content: Content of the post.
        created_at: Timestamp when the post was created.
    """

    __tablename__ = "post"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def as_dict(self):
        """
        Convert the model instance to a dictionary.

        Returns:
            dict: Dictionary representation of the post.
        """
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }

    def serialize(self):
        result = {}
        for col in self.__table__.columns:
            val = getattr(self, col.name)
            if isinstance(val, bytes):
                result[col.name] = base64.b64encode(val).decode()
            elif isinstance(val, (datetime, datetime.date)):
                result[col.name] = val.isoformat()
            else:
                result[col.name] = val
        return result
