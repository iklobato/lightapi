from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import parse_qs, urlparse

from lightapi.db import database
from lightapi.rest import Response


class LightApi:
    def __init__(self):
        self.endpoints = {}
        self.middleware = []
        self._add_default_middleware()

    def _add_default_middleware(self):
        pass

    def register(self, routes):
        self.endpoints.update(routes)

    def add_middleware(self, middleware_classes):
        self.middleware.extend(middleware_classes)

    def run(self, host='localhost', port=8080):
        server_address = (host, port)

        class RequestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.handle_request('GET')

            def do_POST(self):
                self.handle_request('POST')

            def do_PUT(self):
                self.handle_request('PUT')

            def do_DELETE(self):
                self.handle_request('DELETE')

            def do_PATCH(self):
                self.handle_request('PATCH')

            def do_OPTIONS(self):
                self.handle_request('OPTIONS')

            def handle_request(self, method):
                parsed_path = urlparse(self.path)
                endpoint_path = parsed_path.path

                endpoint_class = self.server.lightapi.endpoints.get(endpoint_path)
                if not endpoint_class:
                    self.send_error(404, 'Endpoint not found')
                    return

                query_params = parse_qs(parsed_path.query)
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')

                try:
                    body_data = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    body_data = {}

                db_session = database.create_session()
                request = {
                    'path': endpoint_path,
                    'method': method,
                    'query_params': query_params,
                    'body': body_data,
                    'headers': dict(self.headers),
                    'data': None,
                    'user': None,
                    'db': db_session,
                }

                try:
                    endpoint = endpoint_class()
                    handler_result = endpoint.handle_request(method, request)

                    if isinstance(handler_result, tuple):
                        response_data, status_code = handler_result
                    else:
                        response_data = handler_result
                        status_code = 200  

                    request['db'].commit()

                    response = Response(response_data, status_code)

                    for middleware_class in self.server.lightapi.middleware:
                        middleware = middleware_class()
                        middleware_response = middleware.process(request, response)
                        if middleware_response:
                            response = middleware_response

                except Exception as e:
                    db_session.rollback()
                    response = Response({'error': str(e)}, 500)
                finally:
                    if 'db' in request:
                        try:
                            request['db'].close()
                        except Exception as e:
                            print(f"Error closing session: {e}")

                self.send_response(response.status_code)
                self.send_header('Content-type', response.content_type)
                for key, value in response.headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(json.dumps(response.data).encode('utf-8'))

        server = ThreadingHTTPServer(server_address, RequestHandler)
        server.lightapi = self
        print(f"LightAPI running on http://{host}:{port}")
        server.serve_forever()
