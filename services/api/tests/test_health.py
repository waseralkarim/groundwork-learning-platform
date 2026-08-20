"""Health endpoint tests.

These run without a database — that is the point of the liveness test. If it
needed Postgres to pass, the endpoint would be wrong.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_liveness_reports_alive(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_liveness_does_not_touch_dependencies(client: httpx.AsyncClient) -> None:
    """Regression guard for the classic cascading-restart bug.

    A liveness probe that checks the database turns a database blip into a full
    outage, because every replica fails its probe and restarts at once.
    """
    from app.db import session as session_module

    calls: list[str] = []
    original = session_module.get_sessionmaker

    def spy() -> object:
        calls.append("get_sessionmaker")
        return original()

    session_module.get_sessionmaker = spy  # type: ignore[assignment]
    try:
        await client.get("/v1/health/live")
    finally:
        session_module.get_sessionmaker = original  # type: ignore[assignment]

    assert calls == []


async def test_request_id_is_echoed(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/health/live", headers={"x-request-id": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"


async def test_request_id_is_generated_when_absent(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/health/live")
    assert response.headers.get("x-request-id")
