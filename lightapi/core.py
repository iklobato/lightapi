import json
from typing import Any, Callable, Dict, List, Type

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from .models import Base, setup_database


class LightApi:
    def __init__(
        self,
        database_url: str = "sqlite:///app.db",
        swagger_title: str = "LightAPI Documentation",
        swagger_version: str = "1.0.0",
        swagger_description: str = "API automatic documentation",
        enable_swagger: bool = True,
    ):
        self.routes = []
        self.middleware = []
        self.engine, self.Session = setup_database(database_url)
        self.enable_swagger = enable_swagger

        from .swagger import SwaggerGenerator, openapi_json_route, swagger_ui_route

        if enable_swagger:
            self.swagger_generator = SwaggerGenerator(
                title=swagger_title,
                version=swagger_version,
                description=swagger_description,
            )

            self.routes.append(Route("/api/docs", swagger_ui_route))
            self.routes.append(Route("/openapi.json", openapi_json_route))

    def register(self, endpoints: Dict[str, Type["RestEndpoint"]]):
        for path, endpoint_class in endpoints.items():
            methods = (
                endpoint_class.Configuration.http_method_names
                if hasattr(endpoint_class, 'Configuration')
                and hasattr(endpoint_class.Configuration, 'http_method_names')
                else ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']
            )

            handler = self._create_handler(endpoint_class, methods)
            self.routes.append(Route(path, handler, methods=methods))

            if self.enable_swagger:
                self.swagger_generator.register_endpoint(path, endpoint_class)

    def _create_handler(
        self, endpoint_class: Type["RestEndpoint"], methods: List[str]
    ) -> Callable:
        async def handler(request):
            endpoint = endpoint_class()

            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    body = await request.body()
                    if body:
                        request.data = json.loads(body)
                    else:
                        request.data = {}
                except json.JSONDecodeError:
                    request.data = {}
            else:
                request.data = {}

            endpoint._setup(request, self.Session())

            for middleware_class in self.middleware:
                middleware = middleware_class()
                response = middleware.process(request, None)
                if response:
                    return response

            if hasattr(endpoint, 'headers'):
                request = endpoint.headers(request)

            method = request.method.lower()
            if method in [m.lower() for m in methods] and hasattr(endpoint, method):
                method_handler = getattr(endpoint, method)
                result = method_handler(request)

                if isinstance(result, tuple) and len(result) == 2:
                    response = JSONResponse(content=result[0], status_code=result[1])

                elif isinstance(result, Response):
                    response = result

                else:
                    response = JSONResponse(content=result, status_code=200)

                for middleware_class in self.middleware:
                    middleware = middleware_class()
                    processed_response = middleware.process(request, response)
                    if processed_response:
                        response = processed_response

                return response

            return JSONResponse(
                {"error": f"Method {method.upper()} not allowed"}, status_code=405
            )

        return handler

    def add_middleware(self, middleware_classes: List[Type["Middleware"]]):
        self.middleware = middleware_classes

    def run(self, host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
        app = Starlette(debug=debug, routes=self.routes)

        if self.enable_swagger:
            app.state.swagger_generator = self.swagger_generator

        uvicorn.run(app, host=host, port=port)


class Response(JSONResponse):
    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Dict = None,
        media_type: str = None,
        content_type: str = None,
    ):
        media_type = content_type or media_type or "application/json"
        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
        )


class Middleware:
    def process(self, request, response):
        return response
