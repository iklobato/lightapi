"""paginate_async() is public API that the framework itself no longer calls."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import Field as PydanticField
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request

from lightapi import LightApi, RestEndpoint, get_async_session
from lightapi.pagination import CursorPaginator, PageNumberPaginator, decode_cursor

ROWS = 5
PAGE_SIZE = 2


class PagedGadget(RestEndpoint):
    name: str = PydanticField(min_length=1)


def _get_request(query: bytes) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/pagedgadgets",
            "query_string": query,
            "headers": [],
        }
    )


@pytest_asyncio.fixture
async def seeded_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = LightApi(engine=engine, mode="async")
    app.register({"/pagedgadgets": PagedGadget})
    async with AsyncClient(
        transport=ASGITransport(app=app.build_app()), base_url="http://test"
    ) as client:
        for n in range(ROWS):
            created = await client.post("/pagedgadgets", json={"name": f"gadget-{n}"})
            assert created.status_code == 201
    yield engine
    await engine.dispose()


async def test_page_number_paginate_async_second_page_returns_rows_and_total(
    seeded_engine,
):
    qs = sa_select(PagedGadget).order_by(PagedGadget.id)

    async with get_async_session(seeded_engine) as session:
        rows, total = await PageNumberPaginator().paginate_async(
            _get_request(b"page=2"), qs, session, PAGE_SIZE
        )

    assert total == ROWS
    assert [row.name for row in rows] == ["gadget-2", "gadget-3"]


async def test_cursor_paginate_async_full_page_returns_next_cursor(seeded_engine):
    qs = sa_select(PagedGadget)

    async with get_async_session(seeded_engine) as session:
        rows, next_cursor = await CursorPaginator().paginate_async(
            _get_request(b""), qs, session, PAGE_SIZE
        )

    assert [row.name for row in rows] == ["gadget-0", "gadget-1"]
    assert decode_cursor(next_cursor) == rows[-1].id
