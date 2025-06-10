from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from lightapi.core import LightApi
from lightapi.rest import RestEndpoint, Validator
from lightapi.swagger import SwaggerGenerator


# Validator with method docstrings for better Swagger documentation
class TaskValidator(Validator):
    def validate_title(self, value):
        """
        Validate task title.

        Args:
            value (str): The title to validate

        Returns:
            str: Validated title

        Raises:
            ValueError: If title is empty or too long
        """
        if not value:
            raise ValueError("Title cannot be empty")
        if len(value) > 100:
            raise ValueError("Title cannot exceed 100 characters")
        return value.strip()

    def validate_completed(self, value):
        """
        Validate completed status.

        Args:
            value: The completed status

        Returns:
            bool: Validated status as boolean
        """
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1")
        return bool(value)


# Models with docstrings for better Swagger documentation
class Project(RestEndpoint):
    """
    Project model for task organization.

    Projects contain multiple tasks and provide organization structure.
    """

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, doc="Project name")
    description = Column(Text, doc="Project description")

    # Relationships
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")

    def get(self, request):
        """
        Retrieve projects.

        Returns a list of all projects or a specific project by ID.

        Args:
            request: The HTTP request

        Returns:
            dict: Project data
        """
        return super().get(request)

    def post(self, request):
        """
        Create a new project.

        Args:
            request: The HTTP request with project data

        Returns:
            dict: Created project data

        Raises:
            Exception: If project creation fails
        """
        return super().post(request)


class Task(RestEndpoint):
    """
    Task model for tracking work items.

    Tasks belong to projects and can be assigned priorities and completion status.
    """

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False, doc="Task title")
    description = Column(Text, doc="Detailed task description")
    completed = Column(Boolean, default=False, doc="Whether the task is completed")
    priority = Column(
        Integer, default=1, doc="Task priority (1-5, with 5 being highest)"
    )
    project_id = Column(
        Integer, ForeignKey("projects.id"), doc="ID of the parent project"
    )

    # Relationships
    project = relationship("Project", back_populates="tasks")

    class Configuration:
        validator_class = TaskValidator

    def get(self, request):
        """
        Retrieve tasks.

        Returns a list of all tasks or a specific task by ID.
        Can be filtered by completion status using query parameter '?completed=true|false'.

        Args:
            request: The HTTP request

        Returns:
            dict: Task data
        """
        query = self.session.query(self.__class__)

        # Filter by completion status if specified
        completed_param = request.query_params.get("completed")
        if completed_param is not None:
            completed = completed_param.lower() in ("true", "yes", "1")
            query = query.filter(Task.completed == completed)

        # Filter by project_id if specified
        project_id = request.query_params.get("project_id")
        if project_id and project_id.isdigit():
            query = query.filter(Task.project_id == int(project_id))

        # Execute query
        results = query.all()

        # Format results
        data = []
        for obj in results:
            data.append(
                {
                    "id": obj.id,
                    "title": obj.title,
                    "description": obj.description,
                    "completed": obj.completed,
                    "priority": obj.priority,
                    "project_id": obj.project_id,
                }
            )

        return {"results": data}, 200

    def post(self, request):
        """
        Create a new task.

        Args:
            request: The HTTP request with task data

        Returns:
            dict: Created task data

        Raises:
            Exception: If task creation fails
        """
        return super().post(request)

    def put(self, request):
        """
        Update an existing task.

        Args:
            request: The HTTP request with task data and ID

        Returns:
            dict: Updated task data

        Raises:
            Exception: If task update fails
        """
        return super().put(request)

    def delete(self, request):
        """
        Delete a task.

        Args:
            request: The HTTP request with task ID

        Returns:
            dict: Deletion confirmation

        Raises:
            Exception: If task deletion fails
        """
        return super().delete(request)


# Custom Swagger generator with additional information
class CustomSwaggerGenerator(SwaggerGenerator):
    def __init__(self, title, version, description=None):
        super().__init__(title, version, description)

        # Add custom tags for better organization
        self.tags = [
            {"name": "Projects", "description": "Project management endpoints"},
            {"name": "Tasks", "description": "Task management endpoints"},
        ]

        # Add custom security scheme
        self.security_schemes = {
            "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
        }

    # Add tag information to endpoint paths
    def generate_path_item(self, endpoint_class, path):
        path_item = super().generate_path_item(endpoint_class, path)

        # Add tags based on endpoint type
        if endpoint_class.__name__ == "Project":
            for method in path_item.values():
                if "tags" not in method:
                    method["tags"] = []
                method["tags"].append("Projects")
        elif endpoint_class.__name__ == "Task":
            for method in path_item.values():
                if "tags" not in method:
                    method["tags"] = []
                method["tags"].append("Tasks")

        return path_item


if __name__ == "__main__":
    app = LightApi(
        database_url="sqlite:///swagger_example.db",
        swagger_title="Task Manager API",
        swagger_version="1.0.0",
        swagger_description="""
        # Task Manager API
        
        A RESTful API for managing projects and tasks.
        
        ## Features
        
        - Create and manage projects
        - Create and track tasks within projects
        - Mark tasks as completed
        - Set task priorities
        
        ## Authentication
        
        Some endpoints require authentication with an API key.
        """,
    )

    # Use the custom swagger generator
    app.swagger_generator = CustomSwaggerGenerator(
        title="Swagger API Example",
        version="1.0.0",
        description="Example API with custom Swagger documentation",
    )

    # Register endpoints
    app.register({"/projects": Project, "/tasks": Task})

    print("Server running at http://localhost:8000")
    print("API documentation available at http://localhost:8000/docs")

    app.run(host="localhost", port=8000, debug=True)
