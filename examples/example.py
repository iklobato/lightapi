from sqlalchemy import Column, Integer, String

from lightapi.auth import JWTAuthentication
from lightapi.cache import RedisCache
from lightapi.core import LightApi, Middleware
from lightapi.filters import ParameterFilter
from lightapi.pagination import Paginator
from lightapi.rest import Response, RestEndpoint, Validator


class CustomEndpointValidator(Validator):
    def validate_name(self, value):
        return value

    def validate_email(self, value):
        return value

    def validate_website(self, value):
        return value


class Company(RestEndpoint):
    """Company entity for demonstration purposes.

    This endpoint allows management of company information.
    """

    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    website = Column(String)

    class Configuration:
        validator_class = CustomEndpointValidator
        filter_class = ParameterFilter

    def post(self, request):
        """Create a new company.

        Accepts company data and creates a new record.
        """
        return Response(
            {"data": "ok", "request_data": request.data},
            status_code=200,
            content_type="application/json",
        )

    def get(self, request):
        """Retrieve company information.

        Returns a list of companies or a specific company if ID is provided.
        """
        return {"data": "ok"}, 200

    def headers(self, request):
        request.headers["X-New-Header"] = "my new header value"
        return request


class CustomPaginator(Paginator):
    limit = 100
    sort = True


class CustomEndpoint(RestEndpoint):
    __tablename__ = "custom_endpoints"

    id = Column(Integer, primary_key=True)

    class Configuration:
        http_method_names = ["GET", "POST"]
        authentication_class = JWTAuthentication
        caching_class = RedisCache
        caching_method_names = ["GET"]
        pagination_class = CustomPaginator

    def post(self, request):
        return {"data": "ok"}, 200

    def get(self, request):
        return {"data": "ok"}, 200


class MyCustomMiddleware(Middleware):
    def process(self, request, response):
        if "Authorization" not in request.headers:
            return Response({"error": "not allowed"}, status_code=403)
        return response


class CORSMiddleware(Middleware):
    def process(self, request, response):
        if response is None:
            return None

        if hasattr(response, "headers"):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers[
                "Access-Control-Allow-Methods"
            ] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers[
                "Access-Control-Allow-Headers"
            ] = "Authorization, Content-Type"

        if request.method == "OPTIONS":
            return Response(status_code=200)
        return response


if __name__ == "__main__":
    app = LightApi(
        database_url="sqlite:///example.db",
        swagger_title="LightAPI Example",
        swagger_version="1.0.0",
        swagger_description="Example API for demonstrating LightAPI capabilities",
    )
    app.register({"/companies": Company, "/custom": CustomEndpoint})
    # app.add_middleware([MyCustomMiddleware, CORSMiddleware])

    print("Server running at http://0.0.0.0:8000")
    print("API documentation available at http://0.0.0.0:8000/docs")

    app.run(host="0.0.0.0", port=8000, debug=True)
