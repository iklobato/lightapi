from sqlalchemy import Column, String

from lightapi.core import LightApi, Response, Middleware
from lightapi.rest import RestEndpoint, Validator
from lightapi.pagination import Paginator
from lightapi.auth import JWTAuthentication
from lightapi.filters import ParameterFilter
from lightapi.cache import RedisCache


class CustomEndpointValidator(Validator):
    def validate_name(self, value):
        return value

    def validate_email(self, value):
        return value

    def validate_website(self, value):
        return value


class Company(RestEndpoint):
    name = Column(String)
    email = Column(String, unique=True)
    website = Column(String)

    class Configuration:
        http_method_names = ['GET', 'POST']
        validator_class = CustomEndpointValidator
        filter_class = ParameterFilter

    def post(self, request):
        return Response(
            {'data': 'ok', 'data': getattr(request, 'data', {})},
            status_code=200,
            content_type='application/json'
        )

    def get(self, request):
        return {'data': 'ok'}, 200

    def headers(self, request):
        request.headers['X-New-Header'] = 'my new header value'
        return request


class CustomPaginator(Paginator):
    limit = 100
    sort = True


class CustomEndpoint(RestEndpoint):
    class Configuration:
        http_method_names = ['GET', 'POST']
        authentication_class = JWTAuthentication
        caching_class = RedisCache
        caching_method_names = ['GET']
        pagination_class = CustomPaginator

    def post(self, request):
        return {'data': 'ok'}, 200

    def get(self, request):
        return {'data': 'ok'}, 200


class MyCustomMiddleware(Middleware):
    def process(self, request, response):
        if 'Authorization' not in request.headers:
            return Response({'error': 'not allowed'}, status_code=403)
        return response


class CORSMiddleware(Middleware):
    def process(self, request, response):
        if response is None:
            return None
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
        if request.method == 'OPTIONS':
            return Response(status_code=200)
        return response


def create_app():
    app = LightApi()
    app.register({'/custom': CustomEndpoint})
    app.add_middleware([MyCustomMiddleware, CORSMiddleware])
    return app


if __name__ == '__main__':
    create_app().run()
