---
title: Quickstart
---

This quickstart guide shows you how to create your first LightAPI application in just a few simple steps.

## 1. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2. Install LightAPI

```bash
pip install lightapi
```

## 3. Define a SQLAlchemy Model

```python
# models.py
from sqlalchemy import Column, Integer, String
from lightapi.database import Base

class Item(Base):
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
```

## 4. Create and Run Your App

```python
# main.py
from lightapi import LightApi
from models import Item

app = LightApi()
app.register({'/items': Item})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
```

Now navigate to `http://localhost:8000/items` in your browser or use CURL to interact with the automatically generated CRUD endpoints.
