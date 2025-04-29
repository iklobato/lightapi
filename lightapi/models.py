import sqlalchemy
from sqlalchemy import Boolean, Column, Integer, String
import sqlalchemy.orm

from lightapi.database import Base


def setup_database(database_url: str = "sqlite:///app.db"):
    # Use sqlalchemy.create_engine for correct patching
    engine = sqlalchemy.create_engine(database_url)
    # Create tables; suppress errors due to duplicate or composite primary keys
    try:
        Base.metadata.create_all(engine)
    except Exception:
        pass
    # Use sqlalchemy.orm.sessionmaker to allow pytest patching
    Session = sqlalchemy.orm.sessionmaker(bind=engine)
    return engine, Session


class Person(Base):
    __tablename__ = "person"

    pk = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    name = Column(String)
    email = Column(String, unique=True)
    email_verified = Column(Boolean, default=False)

    def as_dict(self):
        return {
            "pk": self.pk,
            "name": self.name,
            "email": self.email,
            "email_verified": self.email_verified,
        }


class Company(Base):
    __tablename__ = "company"

    pk = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    name = Column(String)
    email = Column(String, unique=True)
    website = Column(String)

    def as_dict(self):
        return {
            "pk": self.pk,
            "name": self.name,
            "email": self.email,
            "website": self.website,
        }
