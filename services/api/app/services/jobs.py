"""Enqueueing background work from a request.

One rule: **a failure to enqueue must never fail the request that triggered it.**
A learner has just submitted a quiz and it graded correctly; if Valkey is
unreachable, the right outcome is a graded quiz and a missing badge, not a 500
and a lost attempt. Every call here is best-effort and logs its own failure.
"""

from __future__ import annotations

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


async def enqueue(function: str, *args: object) -> bool:
    settings = get_settings()
    try:
        pool = await create_pool(
            RedisSettings(host=settings.valkey_host, port=settings.valkey_port)
        )
        try:
            await pool.enqueue_job(function, *args)
        finally:
            await pool.aclose()
        return True
    except Exception:
        log.warning("enqueue_failed", function=function, exc_info=True)
        return False


async def evaluate_achievements_for(user_id: object) -> None:
    """Ask the worker to re-check what this learner has earned."""
    await enqueue("evaluate_achievements", str(user_id))


__all__ = ["enqueue", "evaluate_achievements_for"]
