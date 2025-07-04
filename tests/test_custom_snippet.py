import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from datetime import datetime, timedelta, timezone

import jwt
from starlette.testclient import TestClient

from examples.middleware_cors_auth import Company, CustomEndpoint, create_app
from lightapi.config import config
from lightapi.core import Middleware, Response
from lightapi.lightapi import LightApi


class DummyRedis:
    def __init__(self, *args, **kwargs):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, timeout, value):
        self.store[key] = value
        return True

    def set(self, key, value, **kwargs):
        """Support for set method with optional timeout"""
        self.store[key] = value
        return True


def get_token():
    payload = {"user": "test", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


# test_cors_middleware, test_company_endpoint_functionality, test_request_data_handling, test_http_methods_configuration, and test_pagination_configuration functions removed
