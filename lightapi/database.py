import os

from sqlalchemy import Column, Integer, create_engine
from sqlalchemy.orm import as_declarative, declared_attr, sessionmaker

from .config import config

engine = create_engine(config.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@as_declarative()
class Base:
    """
    Custom SQLAlchemy base class for all models.

    Provides automatic __tablename__ generation and utility methods
    for model instances to make working with SQLAlchemy models easier.

    Attributes:
        __table__: SQLAlchemy table metadata.
        table: Property that returns the table metadata.
        __tablename__: Automatically generated based on class name.
    """

    __table__ = None

    @property
    def table(self):
        """
        Get the table metadata for this model.

        Returns:
            The SQLAlchemy Table object for this model.
        """
        return self.__table__

    @declared_attr
    def __tablename__(cls):
        """
        Generate the table name based on the class name.

        The table name is derived by converting the class name to lowercase.

        Returns:
            str: The generated table name.
        """
        return cls.__name__.lower()

    def serialize(self) -> dict:
        """
        Convert the model instance into a dictionary representation.

        Each key in the dictionary corresponds to a column name, and the value
        is the data stored in that column.

        Returns:
            dict: A dictionary representation of the model instance.
        """
        return {
            column.name: getattr(self, column.name) for column in self.table.columns
        }
