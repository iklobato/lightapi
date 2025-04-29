---
title: Basic CRUD Examples
---

# Basic CRUD Operations

This example demonstrates basic Create, Read, Update, and Delete (CRUD) operations using a LightAPI-generated endpoint for an `Item` model.

## Prerequisites

Assuming you have an `Item` model registered at `/items`:

```python
# app/main.py
from lightapi import LightApi
from sqlalchemy import Column, Integer, String
from lightapi.database import Base

class Item(Base):
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)

app = LightApi()
app.register({'/items': Item})
app.run()
```

## 1. Create an Item

```bash
curl -X POST http://localhost:8000/items/ \
     -H 'Content-Type: application/json' \
     -d '{"name":"Sample Item"}'
```

_Response (201 Created):_
```json
{"id":1,"name":"Sample Item"}
```

## 2. Read All Items

```bash
curl http://localhost:8000/items/
```

_Response (200 OK):_
```json
[{"id":1,"name":"Sample Item"}]
```

## 3. Read a Single Item by ID

```bash
curl http://localhost:8000/items/1
```

_Response (200 OK):_
```json
{"id":1,"name":"Sample Item"}
```

## 4. Update an Item

```bash
curl -X PUT http://localhost:8000/items/1 \
     -H 'Content-Type: application/json' \
     -d '{"name":"Updated Item"}'
```

_Response (200 OK):_
```json
{"result":{"id":1,"name":"Updated Item"}}
```

## 5. Delete an Item

```bash
curl -X DELETE http://localhost:8000/items/1
```

_Response (204 No Content):_ (empty body)

---

## Python Client Example

```python
import requests

base = 'http://localhost:8000/items'

# Create
r = requests.post(base+'/', json={'name':'Hello'})
print(r.json())

# List
r = requests.get(base+'/')
print(r.json())

# Update
r = requests.put(base+'/1', json={'name':'New'})
print(r.json())

# Delete
r = requests.delete(base+'/1')
print(r.status_code)
```
