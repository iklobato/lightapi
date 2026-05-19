"""LightAPI Example 14 - Background Tasks.

Demonstrates:
- self.background() for fire-and-forget tasks
- Async background functions
- Response returned immediately while task runs in background

Prerequisites:
    PostgreSQL with asyncpg driver.

Run with:
    python examples/14_background.py

Then try:
    # Create item - returns immediately, audit runs in background
    curl -X POST http://localhost:8000/items \
        -H 'Content-Type: application/json' \
        -d '{"name":"Test Item"}'

    # Check server console for audit log messages
"""

import logging

from sqlalchemy.ext.asyncio import create_async_engine

from lightapi import HttpMethod, LightApi, RestEndpoint
from lightapi.fields import Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"


async def audit_log(action: str, item_id: int) -> None:
    """Background task that logs actions."""
    logger.info(f"AUDIT: {action} item_id={item_id}")


class ItemEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Endpoint with background tasks."""

    name: str = Field(min_length=1)

    async def post(self, request):
        """Create item and trigger background audit."""
        import json

        data = json.loads((await request.body()).decode())
        response = await self._create_async(data)

        body = json.loads(response.body)
        self.background(audit_log, "created", body["id"])

        return response


if __name__ == "__main__":
    engine = create_async_engine(DATABASE_URL)
    app = LightApi(engine=engine, mode="async")
    app.register({"/items": ItemEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
