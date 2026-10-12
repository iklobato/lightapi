"""Callables that the YAML scenarios reference by dotted path."""

from __future__ import annotations

from typing import Any

from lightapi import Middleware

USERS = {
    "alice": {"password": "secret", "sub": "alice", "is_admin": False, "role": "user"},
    "root": {"password": "toor", "sub": "root", "is_admin": True, "role": "admin"},
}


def check_login(username: str, password: str) -> dict[str, Any] | None:
    user = USERS.get(username)
    if user is None or user["password"] != password:
        return None
    return {key: value for key, value in user.items() if key != "password"}


def exploding_login(username: str, password: str) -> dict[str, Any] | None:
    raise RuntimeError("directory server is down")


async def async_login(username: str, password: str) -> dict[str, Any] | None:
    return None


def one_argument_login(username: str) -> None:
    return None


NOT_CALLABLE = "just a string"


class StampMiddleware(Middleware):
    def process(self, request: Any, response: Any) -> Any:
        if response is not None:
            response.headers["x-trace"] = "stamped"
        return response
