"""Async smoke test — validates all async support acceptance criteria.

Run with: uv run python examples/smoke_async.py
"""
import asyncio
from typing import Optional

import httpx
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication, Filtering, Pagination, Serializer
from lightapi.filters import FieldFilter, OrderingFilter

notified: list[int] = []


async def fake_notify(item_id: int) -> None:
    notified.append(item_id)


class Item(RestEndpoint):
    name: str = Field(min_length=1)
    quantity: int = Field(ge=0)
    secret: str = Field(default="internal")
    notes: Optional[str] = Field(default=None)

    class Meta:
        authentication = Authentication(permission=AllowAny)
        filtering = Filtering(
            backends=[FieldFilter, OrderingFilter],
            fields=["name"],
            ordering=["quantity"],
        )
        pagination = Pagination(page_size=10)
        serializer = Serializer(fields=["id", "name", "quantity", "created_at"])

    async def queryset(self, request):
        return select(type(self)._model_class)

    async def post(self, request):
        import json
        data = json.loads(await request.body())
        response = await self._create_async(data)
        if response.status_code == 201:
            body = json.loads(response.body)
            item_id = body.get("id")
            if item_id is not None:
                self.background(fake_notify, item_id)
        return response


class Category(RestEndpoint):
    name: str = Field(min_length=1, unique=True)
    active: bool = Field(default=True)

    class Meta:
        authentication = Authentication(permission=AllowAny)

    def queryset(self, request):
        return select(type(self)._model_class).where(type(self)._model_class.active.is_(True))


async def run_smoke() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///smoke_async.db")
    app = LightApi(engine=engine)
    app.register({"/items": Item, "/categories": Category})
    starlette_app = app.build_app()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=starlette_app), base_url="http://test"
    ) as c:
        # ── Async endpoint ─────────────────────────────────────────────────
        r = await c.get("/items")
        assert r.status_code == 200, f"GET /items failed: {r.status_code}"
        assert "secret" not in str(r.json()), "secret field leaked in GET response"

        r = await c.post("/items", json={"name": "widget", "quantity": 5})
        assert r.status_code == 201, f"POST /items failed: {r.status_code} body={r.text}"
        assert set(r.json().keys()) == {"id", "name", "quantity", "created_at"}, (
            f"Unexpected keys: {set(r.json().keys())}"
        )

        await asyncio.sleep(0.2)
        assert len(notified) > 0, f"background task did not run; notified={notified}"

        r = await c.post("/items", json={"name": "", "quantity": 5})
        assert r.status_code == 422, f"Expected 422 for empty name, got {r.status_code}"

        r = await c.get("/items", params={"name": "widget"})
        assert r.json()["results"], "filter returned no results"

        r = await c.delete("/items/1")
        assert r.status_code == 204, f"DELETE /items/1 failed: {r.status_code}"
        r = await c.delete("/items/1")
        assert r.status_code == 404, f"Second DELETE should be 404, got {r.status_code}"

        # ── Sync endpoint on same async app ────────────────────────────────
        r = await c.get("/categories")
        assert r.status_code == 200, f"GET /categories failed: {r.status_code}"

        r = await c.post("/categories", json={"name": "tools", "active": True})
        assert r.status_code == 201, f"POST /categories failed: {r.status_code}"

    print("All async smoke assertions passed.")


if __name__ == "__main__":
    asyncio.run(run_smoke())
