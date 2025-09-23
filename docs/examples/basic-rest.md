# Basic REST API Example

This example demonstrates how to create a simple REST API using LightAPI with full CRUD operations, automatic validation, and interactive documentation.

## Overview

We'll build a **Task Management API** that allows you to:
- Create, read, update, and delete tasks
- Automatic input validation
- Interactive Swagger documentation
- Both YAML and Python approaches

## Quick Start (YAML Approach)

### 1. Create Database Schema

```sql
-- tasks.sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    completed BOOLEAN DEFAULT 0,
    priority VARCHAR(20) DEFAULT 'medium',
    due_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data
INSERT INTO tasks (title, description, completed, priority, due_date) VALUES
('Setup development environment', 'Install Python, LightAPI, and dependencies', 1, 'high', '2024-01-15'),
('Write API documentation', 'Create comprehensive API documentation', 0, 'medium', '2024-01-20'),
('Implement user authentication', 'Add JWT authentication to the API', 0, 'high', '2024-01-25'),
('Add task filtering', 'Allow filtering tasks by status and priority', 0, 'low', '2024-01-30');
```

Create the database:
```bash
sqlite3 tasks.db < tasks.sql
```

### 2. Create YAML Configuration

```yaml
# tasks_api.yaml
database_url: "sqlite:///tasks.db"
swagger_title: "Task Management API"
swagger_version: "1.0.0"
swagger_description: |
  Simple task management API with full CRUD operations
  
  ## Features
  - Create, read, update, and delete tasks
  - Automatic input validation
  - Interactive Swagger documentation
  - Filtering and pagination support
  
  ## Usage
  - GET /tasks/ - List all tasks
  - POST /tasks/ - Create a new task
  - GET /tasks/{id} - Get specific task
  - PUT /tasks/{id} - Update entire task
  - PATCH /tasks/{id} - Partially update task
  - DELETE /tasks/{id} - Delete task
enable_swagger: true

tables:
  - name: tasks
    crud: [get, post, put, patch, delete]
```

### 3. Create and Run the API

```python
# app.py
from lightapi import LightApi

# Create API from YAML configuration
app = LightApi.from_config('tasks_api.yaml')

if __name__ == '__main__':
    print("🚀 Starting Task Management API...")
    print("📋 API Documentation: http://localhost:8000/docs")
    print("🔍 API Endpoints: http://localhost:8000/")
    app.run(host='0.0.0.0', port=8000)
```

### 4. Run Your API

```bash
python app.py
```

**That's it!** Your REST API is now running with:
- Full CRUD operations for tasks
- Automatic input validation
- Interactive Swagger documentation at http://localhost:8000/docs
- Proper HTTP status codes and error handling

## API Endpoints

Your API automatically generates these endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tasks/` | List all tasks with pagination |
| GET | `/tasks/{id}` | Get specific task by ID |
| POST | `/tasks/` | Create new task |
| PUT | `/tasks/{id}` | Update entire task record |
| PATCH | `/tasks/{id}` | Partially update task |
| DELETE | `/tasks/{id}` | Delete task |

## Testing Your API

### Using curl

```bash
# Get all tasks
curl http://localhost:8000/tasks/

# Get a specific task
curl http://localhost:8000/tasks/1

# Create a new task
curl -X POST http://localhost:8000/tasks/ \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Learn LightAPI",
    "description": "Go through the documentation and examples",
    "priority": "high",
    "due_date": "2024-02-01"
  }'

# Update a task
curl -X PATCH http://localhost:8000/tasks/1 \
  -H 'Content-Type: application/json' \
  -d '{"completed": true}'

# Delete a task
curl -X DELETE http://localhost:8000/tasks/1
```

### Using Python requests

```python
import requests

BASE_URL = "http://localhost:8000"

# Get all tasks
response = requests.get(f"{BASE_URL}/tasks/")
print("All tasks:", response.json())

# Create a new task
new_task = {
    "title": "Test API with Python",
    "description": "Use requests library to test the API",
    "priority": "medium",
    "due_date": "2024-02-05"
}

response = requests.post(f"{BASE_URL}/tasks/", json=new_task)
print("Created task:", response.json())
task_id = response.json()["id"]

# Update the task
update_data = {"completed": True}
response = requests.patch(f"{BASE_URL}/tasks/{task_id}", json=update_data)
print("Updated task:", response.json())

# Get the updated task
response = requests.get(f"{BASE_URL}/tasks/{task_id}")
print("Task details:", response.json())
```

## Advanced Features

### Filtering and Pagination

```bash
# Pagination
curl "http://localhost:8000/tasks/?page=1&page_size=5"

# Filter by completion status
curl "http://localhost:8000/tasks/?completed=false"

# Filter by priority
curl "http://localhost:8000/tasks/?priority=high"

# Combine filters
curl "http://localhost:8000/tasks/?completed=false&priority=high&page=1&page_size=10"

# Sort results
curl "http://localhost:8000/tasks/?sort=due_date"
curl "http://localhost:8000/tasks/?sort=-created_at"  # Descending
```

### Validation Examples

LightAPI automatically validates requests based on your database schema:

```bash
# This will fail - missing required field
curl -X POST http://localhost:8000/tasks/ \
  -H 'Content-Type: application/json' \
  -d '{"description": "Task without title"}'
# Response: 400 Bad Request - "title is required"

# This will fail - invalid date format
curl -X POST http://localhost:8000/tasks/ \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Invalid Date Task",
    "due_date": "not-a-date"
  }'
# Response: 400 Bad Request - invalid date format
```

## Interactive Documentation

Visit http://localhost:8000/docs to access the interactive Swagger UI where you can:

- **Browse all endpoints**: See all available API operations
- **Test API calls**: Execute requests directly from the browser
- **View schemas**: See request/response data structures
- **Download OpenAPI spec**: Get the API specification file
- **See examples**: View sample requests and responses

## Python Code Approach (Alternative)

If you prefer more control, you can use the Python code approach:

```python
# models.py
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime
from sqlalchemy.sql import func
from lightapi import RestEndpoint

class Task(RestEndpoint):
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    completed = Column(Boolean, default=False)
    priority = Column(String(20), default='medium')
    due_date = Column(Date)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

```python
# app.py
from lightapi import LightApi
from models import Task

# Create the application
app = LightApi(
    database_url="sqlite:///tasks.db",
    swagger_title="Task Management API",
    swagger_version="1.0.0",
    enable_swagger=True,
    cors_origins=["http://localhost:3000"],  # For frontend apps
    debug=True
)

# Register the Task model
app.register({'/tasks': Task})

# Add custom endpoints
@app.get("/tasks/stats")
def get_task_stats():
    """Get task statistics"""
    return {
        "total_tasks": 25,
        "completed_tasks": 12,
        "pending_tasks": 13,
        "high_priority": 5,
        "overdue_tasks": 2
    }

if __name__ == '__main__':
    print("🚀 Starting Task Management API...")
    print("📋 API Documentation: http://localhost:8000/docs")
    app.run(host='0.0.0.0', port=8000)
```

## Response Examples

### Successful Responses

```json
// GET /tasks/
{
  "data": [
    {
      "id": 1,
      "title": "Setup development environment",
      "description": "Install Python, LightAPI, and dependencies",
      "completed": true,
      "priority": "high",
      "due_date": "2024-01-15",
      "created_at": "2024-01-10T10:00:00",
      "updated_at": "2024-01-15T14:30:00"
    }
  ],
  "total": 4,
  "page": 1,
  "page_size": 10
}

// POST /tasks/
{
  "id": 5,
  "title": "Learn LightAPI",
  "description": "Go through the documentation and examples",
  "completed": false,
  "priority": "high",
  "due_date": "2024-02-01",
  "created_at": "2024-01-16T09:15:00",
  "updated_at": "2024-01-16T09:15:00"
}
```

### Error Responses

```json
// 400 Bad Request - Validation Error
{
  "error": "Validation failed",
  "details": {
    "title": ["This field is required"],
    "priority": ["Must be one of: low, medium, high"]
  }
}

// 404 Not Found
{
  "error": "Task not found",
  "message": "Task with id 999 does not exist"
}
```

## Troubleshooting

### Common Issues

**Database connection errors:**
- Ensure your database file exists and is accessible
- Check file permissions
- Verify the database URL format

**Validation errors:**
- Check that required fields are provided
- Ensure data types match the database schema
- Verify foreign key relationships exist

**Import errors:**
- Make sure LightAPI is installed: `pip install lightapi`
- Check Python version compatibility (3.8+)

### Getting Help

- **Documentation**: Check our comprehensive guides
- **GitHub Issues**: [Report bugs or ask questions](https://github.com/iklobato/lightapi/issues)
- **Examples**: Browse more examples in the repository

## Next Steps

Now that you have a basic REST API running:

1. **[Advanced Examples](../examples/)** - Explore more complex use cases
2. **[Authentication Guide](../advanced/authentication.md)** - Secure your API
3. **[Deployment Guide](../deployment/production.md)** - Deploy to production
4. **[Configuration Guide](../getting-started/configuration.md)** - Advanced configuration options

---

**Congratulations!** 🎉 You've successfully created your first REST API with LightAPI. The combination of simplicity and power makes LightAPI perfect for rapid development while maintaining production-ready quality. 