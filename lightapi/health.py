"""Health-check endpoint for container orchestration probes."""

from __future__ import annotations

from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse

HEALTH_PATH = "/healthz"


class HealthCheckEndpoint(HTTPEndpoint):
    """Liveness/readiness probe target.

    Registered at :data:`HEALTH_PATH` on every :class:`~lightapi.lightapi.LightApi`
    app so Kubernetes (and any other orchestrator) can check the process without
    touching a business endpoint. Returns ``200`` with a small JSON body.
    """

    async def get(self, request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})
