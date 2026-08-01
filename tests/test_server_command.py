"""ServerCommand: environment → server configuration."""

import pytest

from lightapi.exceptions import ConfigurationError
from lightapi.server import ServerCommand


def test_from_env_requires_config() -> None:
    with pytest.raises(ConfigurationError):
        ServerCommand.from_env({})


def test_from_env_applies_defaults() -> None:
    cmd = ServerCommand.from_env({"LIGHTAPI_CONFIG": "/etc/lightapi/lightapi.yaml"})
    assert cmd._host == "0.0.0.0"
    assert cmd._port == 8000


def test_from_env_reads_host_and_port() -> None:
    cmd = ServerCommand.from_env(
        {
            "LIGHTAPI_CONFIG": "/c.yaml",
            "LIGHTAPI_HOST": "127.0.0.1",
            "LIGHTAPI_PORT": "9000",
        }
    )
    assert cmd._host == "127.0.0.1"
    assert cmd._port == 9000


def test_from_env_rejects_non_integer_port() -> None:
    with pytest.raises(ConfigurationError):
        ServerCommand.from_env({"LIGHTAPI_CONFIG": "/c.yaml", "LIGHTAPI_PORT": "abc"})
