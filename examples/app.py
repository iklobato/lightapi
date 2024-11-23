from dataclasses import dataclass
from typing import Optional

from lightapi import (
    Validator,
    Paginator,
    RestEndpoint,
    ParameterFilter,
    JWTAuthentication,
    RedisCache,
    Middleware,
    Response,
)
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base

from loader import ConfigurableLightApi

Base = declarative_base()


class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Integer, nullable=False)
    description = Column(String(500))
    is_available = Column(Boolean, default=True)


@dataclass
class ProductSchema:
    name: str
    price: int
    description: Optional[str] = None
    is_available: bool = True


class ProductValidator(Validator):
    async def validate_name(self, value: str) -> str:
        if not value or len(value) < 3:
            raise ValueError("Name must be at least 3 characters long")
        return value.strip()

    async def validate_price(self, value: int) -> int:
        if value < 0:
            raise ValueError("Price cannot be negative")
        return value

    async def validate_description(self, value: Optional[str]) -> Optional[str]:
        if value:
            return value.strip()
        return None


class ProductPaginator(Paginator):
    def __init__(self):
        super().__init__(limit=50, max_limit=200, sort=True)


class ProductEndpoint(RestEndpoint):
    class Configuration:
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
        authentication_class = JWTAuthentication
        authentication_settings = {
            'secret_key': 'your-secret-key-here',
            'algorithm': 'HS256',
            'token_prefix': 'Bearer',
            'exclude_paths': ['/health', '/metrics'],
            'token_expiry_hours': 24
        }
        validator_class = None
        filter_class = None
        pagination_class = None
        caching_class = None
        caching_method_names = []

    async def get(self, request):
        try:

            filters = {
                'is_available': request.query.get('available', True),
                'price__gte': request.query.get('min_price'),
                'price__lte': request.query.get('max_price'),
                'name__like': request.query.get('search'),
            }

            products = await self.filter.filter(Product.query.all(), filters)

            page = int(request.query.get('page', 1))
            items, pagination_info = await self.paginator.paginate(
                products, page=page, sort_by=request.query.get('sort_by', 'name')
            )

            return Response(
                {
                    'data': [ProductSchema.from_orm(item) for item in items],
                    'pagination': pagination_info,
                }
            )

        except Exception as e:
            return Response({'error': str(e)}, status_code=400)

    async def post(self, request):
        try:

            data = await self.validator.validate(request.data)

            product = Product(**data)

            return Response(
                {
                    'message': 'Product created successfully',
                    'data': ProductSchema.from_orm(product),
                },
                status_code=201,
            )

        except ValueError as e:
            return Response({'error': str(e)}, status_code=400)

    async def put(self, request):
        try:
            product_id = request.match_info['id']
            data = await self.validator.validate(request.data)

            product = Product.query.get(product_id)
            if not product:
                return Response({'error': 'Product not found'}, status_code=404)

            for key, value in data.items():
                setattr(product, key, value)

            return Response(
                {
                    'message': 'Product updated successfully',
                    'data': ProductSchema.from_orm(product),
                }
            )

        except Exception as e:
            return Response({'error': str(e)}, status_code=400)


class LoggingMiddleware(Middleware):

    async def process(self, request, handler):
        print(f"[{request.method}] {request.path} - Start")
        try:
            response = await handler(request)
            print(f"[{request.method}] {request.path} - {response.status}")
            return response
        except Exception as e:
            print(f"[{request.method}] {request.path} - Error: {str(e)}")
            raise


class MetricsMiddleware(Middleware):

    async def process(self, request, handler):
        import time

        start_time = time.time()

        response = await handler(request)

        duration = time.time() - start_time
        response.headers['X-Response-Time'] = f"{duration:.3f}s"

        return response


if __name__ == "__main__":

    api = ConfigurableLightApi.from_config('api.yaml')
    api.register({
        '/products': ProductEndpoint,
        '/products/{id}': ProductEndpoint
    })
    api.add_middleware([LoggingMiddleware, MetricsMiddleware])

    api.run(host='0.0.0.0', port=8000)
