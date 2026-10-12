"""e2e app for scenario 10: self.background() with a sync and an async function."""

import asyncio
import json
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request

from lightapi import Field, LightApi, RestEndpoint

MARKS = Path(os.environ["E2E_OUT"]) / "marks"


def mark_sync(item_id: int) -> None:
    (MARKS / f"sync-{item_id}").write_text(str(item_id))


async def mark_async(item_id: int) -> None:
    await asyncio.sleep(0.05)
    (MARKS / f"async-{item_id}").write_text(str(item_id))


class Job(RestEndpoint):
    name: str = Field(min_length=1)

    class Meta:
        table = "e2e10_jobs"

    async def post(self, request: Request):
        response = await self._create_async(json.loads(await request.body()))
        item_id = json.loads(response.body)["id"]
        self.background(mark_sync, item_id)
        self.background(mark_async, item_id)
        return response


def main() -> None:
    MARKS.mkdir(parents=True, exist_ok=True)
    app = LightApi(engine=create_async_engine(os.environ["E2E_DB_URL"]), mode="async")
    app.register({"/jobs": Job})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
