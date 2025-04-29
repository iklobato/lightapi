---
title: Database Models
---

## Base (lightapi.database.Base)

Custom SQLAlchemy declarative base that:

- Automatically generates `__tablename__` from the class name (lowercase).
- Adds a `pk` primary key column to all models.
- Provides a `serialize()` method to convert instances to dicts.

```python
from lightapi.database import Base

class User(Base):
    username = Column(String, unique=True)
```

### setup_database(database_url: str)

Initializes the database engine and session:

- Creates an SQLAlchemy `Engine` with the provided URL.
- Calls `Base.metadata.create_all(engine)` to generate tables.
- Returns `(engine, Session)` where `Session` is a configured sessionmaker.

### SessionLocal and engine

- `engine`: Global SQLAlchemy engine created from `DATABASE_URL` environment variable.
- `SessionLocal`: `sessionmaker` bound to `engine`, used by default handlers to open/close sessions.
