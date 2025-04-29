---
title: First Steps
---

In this guide, you'll explore LightAPI's core concepts by creating a simple project from scratch.

## 1. Project Layout

A minimal project structure might look like:

```
myapp/
├── app/
│   ├── __init__.py
│   ├── models.py
│   └── main.py
├── requirements.txt
└── README.md
```

- **app/models.py**: Define your SQLAlchemy models here.
- **app/main.py**: Create and configure the LightAPI application.

## 2. Defining Your First Model

In `app/models.py`, define a simple `User` model:

```python
# app/models.py
from sqlalchemy import Column, Integer, String
from lightapi.database import Base

class User(Base):
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
```

This class inherits from `Base`, which includes:

- SQLAlchemy metadata
- Default `__tablename__` generation (snake_case of the class name)

## 3. Creating the Application

In `app/main.py`, register the model and start the server:

```python
# app/main.py
from lightapi import LightApi
from app.models import User

app = LightApi()
app.register({
    '/users': User
})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000)
```

- `register` automatically generates CRUD routes (GET, POST, PUT, PATCH, DELETE) for `/users`.
- `run` starts an ASGI server (defaults to Uvicorn under the hood).

## 4. Testing Your Endpoints

Start the app:

```bash
python app/main.py
```

Then, in a separate terminal, try:

```bash
# Create a new user
curl -X POST http://localhost:8000/users/ \
     -H 'Content-Type: application/json' \
     -d '{"username":"alice","email":"alice@example.com"}'

# Get list of users
curl http://localhost:8000/users/

# Retrieve a user by ID
curl http://localhost:8000/users/1
```

You should see JSON responses corresponding to each action.
