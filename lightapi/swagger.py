import inspect
import typing  # noqa: F401
from typing import Any, Dict, List, Type

from sqlalchemy import Column
from sqlalchemy import inspect as sql_inspect
from starlette.responses import HTMLResponse, JSONResponse

from .rest import RestEndpoint


class SwaggerGenerator:
    """
    Generates OpenAPI documentation from LightAPI endpoint classes.

    This class analyzes RestEndpoint classes to extract information about
    their schemas, HTTP methods, validation, and other metadata to build
    a complete OpenAPI specification document.

    Attributes:
        title (str): The title of the API documentation.
        version (str): The API version.
        description (str): A description of the API.
        paths (dict): Endpoint paths and their operations.
        components (dict): Schema definitions and security schemes.
    """

    def __init__(
        self,
        title: str = "LightAPI Documentation",
        version: str = "1.0.0",
        description: str = "API documentation",
    ):
        """
        Initialize a new SwaggerGenerator.

        Args:
            title: The title of the API documentation.
            version: The API version.
            description: A description of the API.
        """
        self.title = title
        self.version = version
        self.description = description
        self.paths = {}
        self.components = {
            "schemas": {},
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            },
        }

    def register_endpoint(self, path: str, endpoint_class: Type[RestEndpoint]):
        """
        Register an endpoint class for OpenAPI documentation.

        Analyzes the endpoint class to extract HTTP methods, schemas,
        and other metadata to include in the OpenAPI documentation.

        Args:
            path: The URL path where the endpoint is mounted.
            endpoint_class: The RestEndpoint class to document.
        """
        methods = (
            endpoint_class.Configuration.http_method_names
            if hasattr(endpoint_class, "Configuration")
            and hasattr(endpoint_class.Configuration, "http_method_names")
            else ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        )

        model_name = endpoint_class.__name__
        self.components["schemas"][model_name] = self._generate_schema(endpoint_class)

        path_operations = {}
        for method in methods:
            method_lower = method.lower()
            if hasattr(endpoint_class, method_lower):
                operation = self._generate_operation(
                    endpoint_class, method_lower, model_name
                )
                path_operations[method_lower] = operation

        self.paths[path] = path_operations

    def _generate_schema(self, endpoint_class: Type[RestEndpoint]) -> Dict[str, Any]:
        """
        Generate an OpenAPI schema from an endpoint class.

        Extracts information about the model fields, their types,
        and validation requirements to create an OpenAPI schema definition.

        Args:
            endpoint_class: The RestEndpoint class to analyze.

        Returns:
            A dict containing the OpenAPI schema definition.
        """
        properties = {}
        required = []

        if (
            hasattr(endpoint_class, "__table__")
            and endpoint_class.__table__ is not None
        ):
            for column in endpoint_class.__table__.columns:
                column_type = self._map_sql_type_to_openapi(column.type)
                properties[column.name] = column_type

                if (
                    not column.nullable
                    and not column.default
                    and not column.server_default
                ):
                    required.append(column.name)
        else:
            for attr_name in dir(endpoint_class):
                if attr_name.startswith("_") or callable(
                    getattr(endpoint_class, attr_name)
                ):
                    continue

                attr = getattr(endpoint_class, attr_name)
                if isinstance(attr, Column):
                    properties[attr_name] = self._map_sql_type_to_openapi(attr.type)

                    if hasattr(attr, "nullable") and not attr.nullable:
                        required.append(attr_name)

        description = ""
        if endpoint_class.__doc__:
            description = inspect.getdoc(endpoint_class)

        return {
            "type": "object",
            "description": description,
            "properties": properties,
            "required": required,
        }

    def _map_sql_type_to_openapi(self, sql_type) -> Dict[str, Any]:
        """
        Map SQLAlchemy column types to OpenAPI data types.

        Args:
            sql_type: SQLAlchemy type object.

        Returns:
            A dict containing the OpenAPI type definition.
        """
        type_map = {
            "INTEGER": {"type": "integer"},
            "BIGINT": {"type": "integer", "format": "int64"},
            "SMALLINT": {"type": "integer"},
            "VARCHAR": {"type": "string"},
            "TEXT": {"type": "string"},
            "BOOLEAN": {"type": "boolean"},
            "FLOAT": {"type": "number", "format": "float"},
            "NUMERIC": {"type": "number"},
            "DATETIME": {"type": "string", "format": "date-time"},
            "DATE": {"type": "string", "format": "date"},
            "TIME": {"type": "string", "format": "time"},
        }

        type_name = sql_type.__class__.__name__.upper()
        if type_name in type_map:
            return type_map[type_name]
        return {"type": "string"}

    def _generate_operation(
        self, endpoint_class: Type[RestEndpoint], method: str, model_name: str
    ) -> Dict[str, Any]:
        """
        Generate an OpenAPI operation object for an endpoint method.

        Args:
            endpoint_class: The RestEndpoint class.
            method: The HTTP method name (lowercase).
            model_name: The model name for reference.

        Returns:
            A dict containing the OpenAPI operation definition.
        """
        method_handler = getattr(endpoint_class, method, None)
        description = ""
        if method_handler and method_handler.__doc__:
            description = inspect.getdoc(method_handler)

        operation = {
            "tags": [model_name],
            "summary": f"{method.upper()} {model_name}",
            "description": description,
            "responses": {
                "200": {
                    "description": "Successful response",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{model_name}"}
                        }
                    },
                },
                "400": {"description": "Bad request"},
                "401": {"description": "Unauthorized"},
                "403": {"description": "Forbidden"},
                "404": {"description": "Not found"},
            },
        }

        if hasattr(endpoint_class, "Configuration") and hasattr(
            endpoint_class.Configuration, "authentication_class"
        ):
            operation["security"] = [{"bearerAuth": []}]

        if method in ["post", "put", "patch"]:
            operation["requestBody"] = {
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{model_name}"}
                    }
                }
            }

        return operation

    def generate_openapi_spec(self) -> Dict[str, Any]:
        """
        Generate the complete OpenAPI specification document.

        Returns:
            A dict containing the full OpenAPI specification.
        """
        return {
            "openapi": "3.0.0",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": self.description,
            },
            "paths": self.paths,
            "components": self.components,
        }

    def get_swagger_ui(self) -> HTMLResponse:
        """
        Generate the Swagger UI HTML page for interactive API documentation.

        Returns:
            An HTMLResponse containing the Swagger UI interface.
        """
        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>LightAPI - Swagger UI</title>
                <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css">
                <style>
                    html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
                    *, *:before, *:after { box-sizing: inherit; }
                    body { margin: 0; background: #fafafa; }
                </style>
            </head>
            <body>
                <div id="swagger-ui"></div>
                <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
                <script>
                    window.onload = function() {
                        window.ui = SwaggerUIBundle({
                            url: "/openapi.json",
                            dom_id: '#swagger-ui',
                            deepLinking: true,
                            presets: [
                                SwaggerUIBundle.presets.apis,
                                SwaggerUIBundle.SwaggerUIStandalonePreset
                            ],
                            layout: "BaseLayout"
                        });
                    }
                </script>
            </body>
            </html>
        """
        )

    def get_openapi_json(self) -> JSONResponse:
        """
        Generate the OpenAPI specification as a JSON response.

        Returns:
            A JSONResponse containing the OpenAPI specification.
        """
        return JSONResponse(self.generate_openapi_spec())


def swagger_ui_route(request):
    """
    Handle requests for the Swagger UI page.

    Args:
        request: The incoming HTTP request.

    Returns:
        The Swagger UI HTML response.
    """
    generator = request.app.state.swagger_generator
    return generator.get_swagger_ui()


def openapi_json_route(request):
    """
    Handle requests for the OpenAPI JSON specification.

    Args:
        request: The incoming HTTP request.

    Returns:
        The OpenAPI specification as JSON.
    """
    generator = request.app.state.swagger_generator
    return generator.get_openapi_json()
