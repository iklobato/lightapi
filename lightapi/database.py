import os

from sqlalchemy import Column, Integer, create_engine
from sqlalchemy.orm import as_declarative, declared_attr, sessionmaker

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lightapi.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL  # , connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@as_declarative()
class Base:
    """
    Custom SQLAlchemy base class that provides automatic `__tablename__` generation
    and a method to convert model instances to dictionaries.

    Attributes:
        id (Column): Primary key column automatically added to all derived models.

    Methods:
        __tablename__(cls):
            Automatically generates the table name from the class name, converted to lowercase.

        as_dict(self):
            Converts the model instance into a dictionary where keys are the column names and values are the corresponding data.
    """

    __table__ = None

    @property
    def table(self):
        return self.__table__

    @declared_attr
    def __tablename__(cls):
        """
        Generates the table name based on the class name.

        The table name is derived by converting the class name to lowercase.

        Returns:
            str: The generated table name.
        """
        return cls.__name__.lower()

    def serialize(self) -> dict:
        """
        Converts the model instance into a dictionary representation.

        Each key in the dictionary corresponds to a column name, and the value is the data stored in that column.

        Returns:
            dict: A dictionary representation of the model instance.
        """
        return {
            column.name: getattr(self, column.name) for column in self.table.columns
        }
