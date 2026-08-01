"""Console entry point: boot a LightApi server from the environment.

Backs the ``lightapi serve`` command and the container image. The Helm chart
sets ``LIGHTAPI_CONFIG`` to the mounted declarative YAML; this command turns the
process environment into a running server, delegating all real work to
:class:`~lightapi.lightapi.LightApi`.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping

from lightapi.exceptions import ConfigurationError
from lightapi.lightapi import LightApi


class ServerCommand:
    """Boots and serves a LightApi instance from environment configuration.

    Single responsibility: translate the process environment into a running
    server. Building the app is delegated to :meth:`LightApi.from_config`,
    serving to :meth:`LightApi.run`.
    """

    DEFAULT_HOST = "0.0.0.0"
    DEFAULT_PORT = 8000

    def __init__(self, config_path: str, host: str, port: int) -> None:
        self._config_path = config_path
        self._host = host
        self._port = port

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> ServerCommand:
        config_path = env.get("LIGHTAPI_CONFIG")
        if not config_path:
            raise ConfigurationError(
                "LIGHTAPI_CONFIG is not set. Point it at the declarative YAML "
                "config file (e.g. /etc/lightapi/lightapi.yaml)."
            )
        host = env.get("LIGHTAPI_HOST") or cls.DEFAULT_HOST
        port = cls._parse_port(env.get("LIGHTAPI_PORT"))
        return cls(config_path, host, port)

    @classmethod
    def _parse_port(cls, raw: str | None) -> int:
        if not raw:
            return cls.DEFAULT_PORT
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigurationError(
                f"LIGHTAPI_PORT must be an integer, got '{raw}'."
            ) from exc

    def execute(self) -> None:
        LightApi.from_config(self._config_path).run(host=self._host, port=self._port)


def main(argv: list[str] | None = None) -> None:
    """Console-script entry point for the ``lightapi`` command."""
    args = sys.argv[1:] if argv is None else argv
    command = args[0] if args else "serve"
    if command != "serve":
        raise SystemExit(f"Unknown command '{command}'. Usage: lightapi serve")
    ServerCommand.from_env(os.environ).execute()
