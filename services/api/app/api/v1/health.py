"""Health endpoints.

The liveness/readiness distinction is drilled into learners in the Kubernetes
track, so these are the reference implementation — including the mistake we
avoid: liveness must NOT check dependencies. A liveness probe that fails because
the database is down restarts every replica and turns a database blip into a
full outage.
"""

from __future__ import annotations

from typing import Literal

import redis.asyncio as redis
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_sessionmaker

router = APIRouter(prefix="/health", tags=["health"])
log = get_logger(__name__)


class LivenessResponse(BaseModel):
    status: Literal["alive"]


class DependencyStatus(BaseModel):
    ok: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, DependencyStatus]


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    """Is the process running? Deliberately touches nothing else."""
    return LivenessResponse(status="alive")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(response: Response) -> ReadinessResponse:
    """Can this instance serve traffic? Checks every hard dependency."""
    checks: dict[str, DependencyStatus] = {}

    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = DependencyStatus(ok=True)
    except Exception as exc:
        checks["database"] = DependencyStatus(ok=False, detail=type(exc).__name__)

    client = redis.from_url(get_settings().valkey_url)
    try:
        await client.ping()
        checks["cache"] = DependencyStatus(ok=True)
    except Exception as exc:
        checks["cache"] = DependencyStatus(ok=False, detail=type(exc).__name__)
    finally:
        await client.aclose()

    ready = all(check.ok for check in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        log.warning("readiness_failed", checks={k: v.ok for k, v in checks.items()})

    return ReadinessResponse(status="ready" if ready else "not_ready", checks=checks)
