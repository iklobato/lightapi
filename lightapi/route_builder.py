"""Route builder service for LightAPI.

Extracts route creation logic from LightApi class for better SRP.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from starlette.routing import Route

logger = logging.getLogger(__name__)


class RouteBuilder:
    """Builds Starlette routes from RestEndpoint classes.

    Separates route creation logic from the main LightApi class.
    """

    def __init__(self) -> None:
        self._routes: list[Route] = []
        self._endpoint_map: dict[str, type] = {}

    @property
    def routes(self) -> list[Route]:
        return self._routes

    @property
    def endpoint_map(self) -> dict[str, type]:
        return self._endpoint_map

    def register(
        self,
        mapping: dict[str, type],
        make_collection_handler: Callable,
        make_detail_handler: Callable,
        session_manager: Any = None,
    ) -> None:
        """Register endpoint classes as routes.

        Args:
            mapping: Dict of path -> endpoint class
            make_collection_handler: Factory function for collection handlers
            make_detail_handler: Factory function for detail handlers
            session_manager: Session manager to inject
        """
        for path, cls in mapping.items():
            # Inject session manager
            if session_manager is not None:
                cls._session_manager = session_manager

            logger.info(f"Registering endpoint {path} -> {cls.__name__}")
            logger.debug(f"  SQLAlchemy metadata: {cls._meta}")

            allowed = cls._allowed_methods

            collection_route = Route(
                path,
                endpoint=self._make_collection_handler(cls, make_collection_handler),
                methods=[m for m in allowed if m in {"GET", "POST"}],
            )
            detail_route = Route(
                path.rstrip("/") + "/{id:int}",
                endpoint=self._make_detail_handler(cls, make_detail_handler),
                methods=[m for m in allowed if m in {"GET", "PUT", "PATCH", "DELETE"}],
            )

            self._routes.extend([collection_route, detail_route])
            self._endpoint_map[path] = cls

    def _make_collection_handler(
        self,
        cls: type,
        make_handler: Callable,
    ) -> Any:
        """Create a collection handler for the endpoint."""
        return make_handler(cls)

    def _make_detail_handler(
        self,
        cls: type,
        make_handler: Callable,
    ) -> Any:
        """Create a detail handler for the endpoint."""
        return make_handler(cls)

    def clear(self) -> None:
        """Clear all registered routes."""
        self._routes.clear()
        self._endpoint_map.clear()
