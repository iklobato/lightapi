---
title: Creating a Basic API
---

In this tutorial, you'll learn how to build a simple CRUD API using LightAPI with minimal code.

## 1. Define Your Model

Create a SQLAlchemy model that inherits from `Base`:

```python
# app/models.py
from sqlalchemy import Column, Integer, String
from lightapi.database import Base

class Book(Base):
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    author = Column(String, nullable=False)
```

## 2. Create the App and Register the Model

In your main application file, register the model with a route path:

```python
# app/main.py
from lightapi import LightApi
from app.models import Book

app = LightApi()
app.register({'/books': Book})

if __name__ == '__main__':
    app.run()
```

LightAPI will automatically generate the following endpoints:

- `POST /books/` — Create a new `Book` record
- `GET /books/` — List all books
- `GET /books/{id}` — Retrieve a book by ID
- `PUT /books/{id}` — Replace a book by ID
- `PATCH /books/{id}` — Partially update a book
- `DELETE /books/{id}` — Delete a book by ID
- `OPTIONS` and `HEAD` methods for each route

## 3. Try It Out

```bash
# Create a book
curl -X POST http://localhost:8000/books/ \
     -H 'Content-Type: application/json' \
     -d '{"title":"1984","author":"George Orwell"}'

# List books
curl http://localhost:8000/books/
```
