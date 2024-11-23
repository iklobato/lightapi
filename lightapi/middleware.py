import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional

from aiohttp import web
from starlette.responses import Response


class Middleware:
    async def process(self, request: web.Request, handler) -> web.Response:
        response = await handler(request)
        if isinstance(response, Response):
            return await response.to_response()
        if isinstance(response, tuple):
            data, status_code = response
            response = Response(data, status_code)
            return await response.to_response()
        return response


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
