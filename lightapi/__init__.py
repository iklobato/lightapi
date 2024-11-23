from asyncio import Lock
from typing import Any, Type, Union, Iterable, Set
from dataclasses import dataclass
from datetime import timedelta
import jwt
import asyncio_redis
import hashlib
from math import ceil

from typing import Dict, List, Optional
import json
import time
from datetime import datetime
from aiohttp import web
import logging

from starlette.middleware import Middleware


class LoggingMiddleware:

    def __init__(
        self,
        log_request_body: bool = False,
        log_response_body: bool = False,
        exclude_paths: List[str] = None,
        mask_headers: List[str] = None,
        logger: logging.Logger = None,
    ):

        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.exclude_paths = exclude_paths or ['/health', '/metrics']
        self.mask_headers = [
            h.lower()
            for h in (mask_headers or ['Authorization', 'Cookie', 'X-API-Key'])
        ]

        if logger is None:
            self.logger = logging.getLogger('api.access')
            self.logger.setLevel(logging.INFO)

            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
        else:
            self.logger = logger

    def _mask_headers(self, headers: Dict) -> Dict:
        masked = headers.copy()
        for header, value in headers.items():
            if header.lower() in self.mask_headers:
                masked[header] = '********'
        return masked

    def _should_log(self, request: web.Request) -> bool:
        return not any(request.path.startswith(path) for path in self.exclude_paths)

    async def _get_request_body(self, request: web.Request) -> Optional[str]:
        if not self.log_request_body or not request.can_read_body:
            return None

        try:
            body = await request.text()

            try:
                json_body = json.loads(body)
                return json.dumps(json_body, indent=2)
            except json.JSONDecodeError:
                return body if body else None
        except Exception as e:
            self.logger.warning(f"Error reading request body: {str(e)}")
            return None

    async def _get_response_body(self, response: web.Response) -> Optional[str]:
        if not self.log_response_body:
            return None

        try:

            if isinstance(response, web.Response):
                body = response.body.decode() if response.body else None
                if body and response.content_type == 'application/json':
                    try:
                        json_body = json.loads(body)
                        return json.dumps(json_body, indent=2)
                    except json.JSONDecodeError:
                        return body
                return body
            return None
        except Exception as e:
            self.logger.warning(f"Error reading response body: {str(e)}")
            return None

    def _format_log_entry(
        self,
        request: web.Request,
        response: web.Response,
        duration: float,
        request_body: Optional[str] = None,
        response_body: Optional[str] = None,
        error: Optional[Exception] = None,
    ) -> Dict:
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'request': {
                'id': getattr(request, 'id', None),
                'method': request.method,
                'path': str(request.url),
                'query_string': str(request.query_string),
                'headers': self._mask_headers(dict(request.headers)),
                'remote': request.remote,
                'user_agent': request.headers.get('User-Agent'),
            },
            'response': {
                'status': getattr(response, 'status', 500 if error else None),
                'headers': self._mask_headers(dict(getattr(response, 'headers', {}))),
                'content_type': getattr(response, 'content_type', None),
            },
            'duration': f"{duration:.3f}s",
            'user': getattr(request, 'user', None),
        }

        if request_body:
            log_entry['request']['body'] = request_body
        if response_body:
            log_entry['response']['body'] = response_body

        if error:
            log_entry['error'] = {
                'type': type(error).__name__,
                'message': str(error),
            }

        return log_entry

    async def process(self, request: web.Request, handler) -> web.Response:
        if not self._should_log(request):
            return await handler(request)

        start_time = time.time()
        request_body = await self._get_request_body(request)
        error = None
        response = None

        try:

            response = await handler(request)
            return response

        except Exception as e:
            error = e

            response = web.Response(text=str(e), status=500, content_type='text/plain')
            raise

        finally:
            duration = time.time() - start_time

            response_body = (
                await self._get_response_body(response) if response else None
            )

            log_entry = self._format_log_entry(
                request=request,
                response=response,
                duration=duration,
                request_body=request_body,
                response_body=response_body,
                error=error,
            )

            if error:
                self.logger.error(json.dumps(log_entry, indent=2))
            elif response.status >= 400:
                self.logger.warning(json.dumps(log_entry, indent=2))
            else:
                self.logger.info(json.dumps(log_entry, indent=2))


@dataclass
class PaginationInfo:
    page: int
    limit: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


class Response:
    def __init__(
        self,
        data: Dict = None,
        status_code: int = 200,
        content_type: str = 'application/json',
    ):
        self.data = data if data is not None else {}
        self.status_code = status_code
        self.content_type = content_type
        self.headers = {}

    async def to_response(self) -> web.Response:
        return web.json_response(
            self.data, status=self.status_code, headers=self.headers
        )


class JWTAuthentication:
    def __init__(
        self,
        secret_key: str,
        algorithm: str = 'HS256',
        token_prefix: str = 'Bearer',
        exclude_paths: Optional[List[str]] = None,
        token_expiry_hours: int = 24,
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_prefix = token_prefix
        self.exclude_paths = exclude_paths or []
        self.token_expiry_hours = token_expiry_hours

    async def authenticate(self, request: web.Request) -> bool:
        if any(request.path.startswith(path) for path in self.exclude_paths):
            return True

        try:
            auth_header = request.headers.get('Authorization', '')
            if not auth_header:
                return False

            parts = auth_header.split()
            if len(parts) != 2 or parts[0] != self.token_prefix:
                return False

            token = parts[1]
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            exp = payload.get('exp')
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                return False

            request['user'] = payload
            return True

        except jwt.InvalidTokenError:
            return False
        except Exception:

            return False

    def generate_token(
        self, payload: Dict[str, Any], expires_in: Optional[int] = None
    ) -> str:

        token_payload = payload.copy()

        expiry_hours = expires_in if expires_in is not None else self.token_expiry_hours
        exp = datetime.utcnow() + timedelta(hours=expiry_hours)
        token_payload['exp'] = exp

        return jwt.encode(token_payload, self.secret_key, algorithm=self.algorithm)


class RedisCache:
    def __init__(
        self,
        redis_url: str = 'redis://localhost',
        ttl: int = 300,
        prefix: str = 'api:cache:',
    ):
        self._lock = Lock()
        self.redis_url = redis_url
        self.ttl = ttl
        self.prefix = prefix
        self._redis = None

    async def _get_redis(self) -> asyncio_redis.Connection:
        if self._redis is None:
            self._redis = await asyncio_redis.Connection.create(self.redis_url)
        return self._redis

    def _get_cache_key(self, request: web.Request) -> str:
        key_parts = [
            request.method,
            str(request.url),
            str(request.query_string),
            str(getattr(request, 'user', '')),
        ]

        if request.method in ['POST', 'PUT'] and hasattr(request, 'data'):
            key_parts.append(json.dumps(request.data, sort_keys=True))

        key_string = '|'.join(key_parts)
        hashed_key = hashlib.sha256(key_string.encode()).hexdigest()
        return f"{self.prefix}{hashed_key}"

    async def get(self, request: web.Request) -> Optional[Response]:
        redis = await self._get_redis()
        cache_key = self._get_cache_key(request)
        cached_data = await redis.get(cache_key)

        if cached_data:
            data = json.loads(cached_data)
            return Response(
                data=data['body'],
                status_code=data['status'],
                headers=data.get('headers', {}),
            )
        return None

    async def set(self, request: web.Request, response: Response) -> None:
        redis = await self._get_redis()
        cache_key = self._get_cache_key(request)

        cache_data = {
            'body': response.data,
            'status': response.status_code,
            'headers': response.headers,
        }

        await redis.set(cache_key, json.dumps(cache_data), expire=self.ttl)

    async def invalidate(self, pattern: str = None) -> None:
        redis = await self._get_redis()
        pattern = f"{self.prefix}{pattern or ''}*"
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)

    async def close(self) -> None:
        if self._redis is not None:
            self._redis.close()
            await self._redis.wait_closed()
            self._redis = None


class Paginator:
    def __init__(self, limit: int = 20, max_limit: int = 100, sort: bool = False):
        self.default_limit = limit
        self.max_limit = max_limit
        self.sort = sort
        self.default_limit = max(1, min(limit, max_limit))

    async def paginate(
        self,
        items: List[Any],
        page: int = 1,
        sort_by: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> tuple[List[Any], PaginationInfo]:

        if not isinstance(items, Iterable):
            raise ValueError("Items must be iterable")

        page = max(1, page)
        limit = min(limit or self.default_limit, self.max_limit)

        total = len(items)
        total_pages = ceil(total / limit)

        if self.sort and sort_by:
            reverse = False
            if sort_by.startswith('-'):
                sort_by = sort_by[1:]
                reverse = True
            items = sorted(
                items, key=lambda x: getattr(x, sort_by, None), reverse=reverse
            )

        start = (page - 1) * limit
        end = min(start + limit, total)

        paginated_items = items[start:end]

        pagination_info = PaginationInfo(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

        return paginated_items, pagination_info


class ParameterFilter:
    def __init__(self, allowed_fields: Optional[List[str]] = None) -> None:
        self.allowed_fields: Set[str] = set(allowed_fields or [])
        self.operators: Dict[str, Any] = {
            'eq': self._equals,
            'neq': self._not_equals,
            'gt': self._greater_than,
            'gte': self._greater_than_equals,
            'lt': self._less_than,
            'lte': self._less_than_equals,
            'like': self._contains,
            'in': self._is_in,
            'nin': self._not_in,
            'startswith': self._starts_with,
            'endswith': self._ends_with,
        }

    def _check_none(self, x: Any, y: Any) -> bool:
        return x is None or y is None

    def _equals(self, x: Any, y: Any) -> bool:
        return x == y

    def _not_equals(self, x: Any, y: Any) -> bool:
        return x != y

    def _greater_than(self, x: Any, y: Any) -> bool:
        if self._check_none(x, y):
            return False
        try:
            return x > y
        except TypeError:
            return False

    def _greater_than_equals(self, x: Any, y: Any) -> bool:
        if self._check_none(x, y):
            return False
        try:
            return x >= y
        except TypeError:
            return False

    def _less_than(self, x: Any, y: Any) -> bool:
        if self._check_none(x, y):
            return False
        try:
            return x < y
        except TypeError:
            return False

    def _less_than_equals(self, x: Any, y: Any) -> bool:
        if self._check_none(x, y):
            return False
        try:
            return x <= y
        except TypeError:
            return False

    def _contains(self, x: Any, y: Any) -> bool:
        if self._check_none(x, y):
            return False
        return str(y).lower() in str(x).lower()

    def _is_in(self, x: Any, y: Any) -> bool:
        try:
            return x in y
        except TypeError:
            return False

    def _not_in(self, x: Any, y: Any) -> bool:
        try:
            return x not in y
        except TypeError:
            return False

    def _starts_with(self, x: Any, y: Any) -> bool:
        if self._check_none(x, y):
            return False
        return str(x).lower().startswith(str(y).lower())

    def _ends_with(self, x: Any, y: Any) -> bool:
        if self._check_none(x, y):
            return False
        return str(x).lower().endswith(str(y).lower())

    def _parse_value(self, value: str) -> Any:
        if not isinstance(value, str):
            return value

        value_lower = value.lower()
        if value_lower == 'true':
            return True
        if value_lower == 'false':
            return False
        if value_lower == 'null':
            return None

        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value

    def _get_field_value(self, item: Any, field: str) -> Any:
        value = item
        for part in field.split('.'):
            value = getattr(value, part, None)
            if value is None:
                break
        return value

    async def filter(self, queryset: List[Any], params: Dict[str, Any]) -> List[Any]:
        if not params:
            return queryset

        filtered = queryset
        for param, value in params.items():
            if '__' in param:
                field, operator = param.rsplit('__', 1)
                if operator not in self.operators:
                    field = param
                    operator = 'eq'
            else:
                field = param
                operator = 'eq'

            if field in self.allowed_fields:
                parsed_value = self._parse_value(value)
                filtered = [
                    item
                    for item in filtered
                    if self.operators[operator](
                        self._get_field_value(item, field), parsed_value
                    )
                ]

        return filtered


class CORSMiddleware:

    def __init__(
        self,
        allow_origins: Union[List[str], str] = '*',
        allow_methods: List[str] = None,
        allow_headers: List[str] = None,
        allow_credentials: bool = False,
        expose_headers: List[str] = None,
        max_age: int = 86400,
    ):
        self.allow_origins = allow_origins
        self.allow_methods = allow_methods or [
            'GET',
            'POST',
            'PUT',
            'DELETE',
            'OPTIONS',
        ]
        self.allow_headers = allow_headers or [
            'Authorization',
            'Content-Type',
            'X-Requested-With',
        ]
        self.allow_credentials = allow_credentials
        self.expose_headers = expose_headers or []
        self.max_age = max_age

    def _get_origin(self, request: web.Request) -> Optional[str]:
        origin = request.headers.get('Origin')
        if not origin:
            return None

        if self.allow_origins == '*':
            return origin

        if origin in self.allow_origins:
            return origin

        return None

    async def process(self, request: web.Request, handler) -> web.Response:
        origin = self._get_origin(request)

        if request.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Methods': ','.join(self.allow_methods),
                'Access-Control-Allow-Headers': ','.join(self.allow_headers),
                'Access-Control-Max-Age': str(self.max_age),
            }

            if origin:
                headers['Access-Control-Allow-Origin'] = origin

            if self.allow_credentials:
                headers['Access-Control-Allow-Credentials'] = 'true'

            if self.expose_headers:
                headers['Access-Control-Expose-Headers'] = ','.join(self.expose_headers)

            return web.Response(status=204, headers=headers)

        response = await handler(request)

        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin

        if self.allow_credentials:
            response.headers['Access-Control-Allow-Credentials'] = 'true'

        if self.expose_headers:
            response.headers['Access-Control-Expose-Headers'] = ','.join(
                self.expose_headers
            )

        return response


class Validator:
    async def validate(self, data: Dict) -> Dict:
        validated_data = {}
        for field, value in data.items():
            validator_method = getattr(self, f'validate_{field}', None)
            if validator_method:
                validated_data[field] = await validator_method(value)
            else:
                validated_data[field] = value
        return validated_data


class RestEndpoint:
    class Configuration:
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
        authentication_class = None
        authentication_settings = {}
        validator_class = None
        filter_class = None
        pagination_class = None
        caching_class = None
        caching_method_names = []

    def __init__(self):
        self.auth = (
            self.Configuration.authentication_class(**self.Configuration.authentication_settings)
            if self.Configuration.authentication_class
            else None
        )
        self.validator = (
            self.Configuration.validator_class()
            if self.Configuration.validator_class
            else None
        )
        self.filter = (
            self.Configuration.filter_class()
            if self.Configuration.filter_class
            else None
        )
        self.paginator = (
            self.Configuration.pagination_class()
            if self.Configuration.pagination_class
            else None
        )
        self.cache = (
            self.Configuration.caching_class()
            if self.Configuration.caching_class
            else None
        )

    async def dispatch(self, request: web.Request) -> web.Response:
        if self.auth and not await self.auth.authenticate(request):
            response = Response({'error': 'Unauthorized'}, 401)
            return await response.to_response()

        method = request.method.lower()
        if method not in [m.lower() for m in self.Configuration.http_method_names]:
            response = Response({'error': 'Method not allowed'}, 405)
            return await response.to_response()

        handler = getattr(self, method, None)
        if not handler:
            response = Response({'error': 'Method not implemented'}, 501)
            return await response.to_response()

        if self.cache and method in [
            m.lower() for m in self.Configuration.caching_method_names
        ]:
            cached_response = await self.cache.get(request)
            if cached_response:
                return await cached_response.to_response()

        if request.content_type == 'application/json':
            try:
                request.data = await request.json()
                if self.validator:
                    request.data = await self.validator.validate(request.data)
            except json.JSONDecodeError:
                response = Response({'error': 'Invalid JSON'}, 400)
                return await response.to_response()

        response = await handler(request)

        if isinstance(response, tuple):
            data, status_code = response
            response = Response(data, status_code)
        elif not isinstance(response, Response):
            response = Response(response)

        if self.cache and method in [
            m.lower() for m in self.Configuration.caching_method_names
        ]:
            await self.cache.set(request, response)

        return await response.to_response()


class LightApi:
    def __init__(self):
        self.app = web.Application()
        self.middlewares = []

    def register(self, routes: Dict[str, Type[RestEndpoint]]):
        for path, endpoint_class in routes.items():
            endpoint = endpoint_class()
            self.app.router.add_route('*', path, endpoint.dispatch)

    def add_middleware(self, middleware_classes: List[Type[Middleware]]):
        @web.middleware
        async def middleware_handler(request, handler):
            for middleware_class in middleware_classes:
                handler = middleware_class().process
            return await handler(request, handler)

        self.app.middlewares.append(middleware_handler)

    def run(self, host: str = 'localhost', port: int = 8080):
        web.run_app(self.app, host=host, port=port)
