import time
from collections import defaultdict


class Middleware:
    def process(self, request, response):
        return response


class CORSMiddleware(Middleware):
    def process(self, request, response):
        if 'headers' not in response:
            response['headers'] = {}
            
        response['headers'].update({
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Authorization, Content-Type',
        })
        return response


class RateLimitingMiddleware(Middleware):
    def __init__(self, limit=100, window=60):
        self.limit = limit
        self.window = window
        self.requests = defaultdict(list)

    def process(self, request, response):
        client_ip = request.get('headers', {}).get('X-Forwarded-For', '127.0.0.1')
        now = time.time()

        self.requests[client_ip] = [
            t for t in self.requests[client_ip] if now - t < self.window
        ]

        if len(self.requests[client_ip]) >= self.limit:
            response['data'] = {'error': 'Rate limit exceeded'}
            response['status_code'] = 429
            return response

        self.requests[client_ip].append(now)
        return response


class DatabaseMiddleware(Middleware):
    def process(self, request, response):
        from .db import database

        request['db'] = database.session
        try:
            return response
        finally:
            database.session.close()

