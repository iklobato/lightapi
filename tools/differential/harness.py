"""Shared pieces of the differential harness: recorder, clients, fake Redis.

Everything here must run unchanged on the oldest version being compared, so it
only uses API that the README documents.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

JWT_SECRET = "differential-harness-secret"

# The only things allowed to differ between two runs of the same code.
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?")
_JWT = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+")

_KEPT_HEADERS = (
    "content-type",
    "allow",
    "www-authenticate",
    "retry-after",
    "location",
    "x-trace",
)
_KEPT_HEADER_PREFIXES = ("access-control-", "x-ratelimit-")


def normalise(text: str) -> str:
    return _JWT.sub("<jwt>", _TIMESTAMP.sub("<timestamp>", text))


def _stable_header(name: str, value: str) -> str:
    # Starlette builds Allow from a set, so its order changes with the process
    # hash seed; the reset header is wall-clock time.
    if name == "allow":
        return ", ".join(sorted(part.strip() for part in value.split(",")))
    if name == "x-ratelimit-reset":
        return "<epoch>"
    return normalise(value)


class Recorder:
    """Collects what each scenario step observed, in order."""

    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []

    def http(self, step_id: str, response: Any) -> Any:
        headers = {
            name: _stable_header(name, value)
            for name, value in sorted(response.headers.items())
            if name in _KEPT_HEADERS or name.startswith(_KEPT_HEADER_PREFIXES)
        }
        self.steps.append(
            {
                "id": step_id,
                "status": int(response.status_code),
                "headers": headers,
                # Raw text, not parsed JSON: key order is part of the contract.
                "body": normalise(response.text),
            }
        )
        return response

    def note(self, step_id: str, value: Any) -> None:
        self.steps.append({"id": step_id, "value": value})

    def raised(self, step_id: str, error: BaseException) -> None:
        self.note(step_id, f"{type(error).__name__}: {normalise(str(error))}")


class FakeRedis:
    """The five calls lightapi makes on a Redis client, backed by a dict."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> bool:
        self.store[key] = value
        return True

    def delete(self, *keys: str) -> int:
        return sum(self.store.pop(key, None) is not None for key in keys)

    def scan_iter(self, pattern: str) -> list[str]:
        prefix = pattern.rstrip("*")
        return [key for key in list(self.store) if key.startswith(prefix)]

    def ping(self) -> bool:
        return True


def install_fake_redis() -> FakeRedis:
    """Make every Redis client lightapi builds from now on the same FakeRedis."""
    import redis

    fake = FakeRedis()
    redis.from_url = lambda *args, **kwargs: fake  # type: ignore[assignment]
    return fake


def memory_engine() -> Any:
    return create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )


def client_for(app: Any) -> TestClient:
    # A 500 is recorded like any other response instead of aborting the run.
    return TestClient(app.build_app(), raise_server_exceptions=False)


def bearer(payload: dict[str, Any], expiration: int | None = None) -> dict[str, str]:
    from lightapi import JWTAuthentication

    token = JWTAuthentication().generate_token(payload, expiration=expiration)
    return {"Authorization": f"Bearer {token}"}
