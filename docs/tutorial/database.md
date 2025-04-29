---
title: Database Integration
---

LightAPI integrates seamlessly with SQLAlchemy's async support. In this tutorial, you'll configure your database connection, define models, create tables, and use async sessions in your endpoints.

## 1. Configure the Database URL

When creating your `LightApi` instance, pass the `database_url` parameter:

```python
# main.py
from lightapi import LightApi

app = LightApi(
    database_url="sqlite+aiosqlite:///./app.db"
)
```

Supported URL schemes include:

- `sqlite+aiosqlite:///<path>`
- `postgresql+asyncpg://user:pass@host/dbname`
- `mysql+aiomysql://user:pass@host/dbname`

## 2. Define Models and Create Tables

LightAPI uses a shared `Base` metadata. After defining your SQLAlchemy models, you can create tables using the built-in helper:

```python
# app/models.py
from sqlalchemy import Column, Integer, String
from lightapi.database import Base

class Task(Base):
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    completed = Column(Boolean, default=False)
```

To create tables at startup, use an event handler:

```python
# app/main.py
from lightapi import LightApi
from lightapi.database import Base, engine
from app.models import Task

app = LightApi(database_url="sqlite+aiosqlite:///./app.db")

@app.on_event("startup")
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.register({"/tasks": Task})
``` 

## 3. Using Async Sessions in Custom Endpoints

If you need direct access to the session, inject it into your custom endpoint:

```python
# app/endpoints/custom_task.py
from lightapi.rest import RestEndpoint

class CustomTaskEndpoint(RestEndpoint):
    tablename = "tasks"

    async def get(self, request):
        # `self.session` is an async SQLAlchemy session
        tasks = await self.session.execute(
            select(Task).order_by(Task.id)
        )
        return [t._asdict() for t in tasks.scalars().all()]
```

Register:
```python
app.register({"/custom-tasks": CustomTaskEndpoint})
```

## 4. Alembic Migrations (Optional)

LightAPI doesn't include migrations out of the box, but you can configure Alembic using the same `database_url`. Initialize Alembic in your project and point `alembic.ini` to `env.py` that imports `Base.metadata`:

```ini
# alembic.ini
sqlalchemy.url = sqlite+aiosqlite:///./app.db
```
