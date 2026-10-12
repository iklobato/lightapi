"""The ten `proposta` rows of docs/audit.md, applied on 2026-10-12 at Henry's request.

One class per row. Each test names the behaviour a reasonable user of the
documented feature gets after the fix, and failed before it.
"""

from __future__ import annotations

import asyncio
import base64
import datetime
from unittest.mock import patch

import jwt
import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import (
    AllowAny,
    Authentication,
    BasicAuthentication,
    Cache,
    Field,
    Filtering,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    RateLimiter,
    RestEndpoint,
)
from lightapi.config import config
from lightapi.core import CORSMiddleware
from lightapi.exceptions import ConfigurationError
from lightapi.filters import BaseFilter


def _memory_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _basic_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


class TestB1001DictConfigUnknownAuth:
    """B1-001: an `auth:` value the dict config does not know was dropped and the
    endpoint served without a backend; it is a ConfigurationError naming it."""

    def test_unknown_auth_kind_is_refused(self):
        document = {
            "endpoints": {"/things": {"fields": {"title": str}, "auth": "oauth"}}
        }

        with (
            pytest.warns(DeprecationWarning),
            pytest.raises(ConfigurationError, match="oauth"),
        ):
            LightApi.from_dict(document, engine=_memory_engine())
