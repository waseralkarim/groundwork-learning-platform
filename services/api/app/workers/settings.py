"""Background worker.

Achievement evaluation runs here rather than in the request that triggers it.
Evaluating every rule means walking every published topic and scoring every
objective, which is fine at three topics and not fine at fifty — and none of it
is work the learner is waiting for. Submitting a quiz should not get slower
because the platform grew.

The trade-off is that an achievement appears a second or two after the action
that earned it. That is the right way round: a slow submit is felt immediately,
a slightly late badge is not felt at all.
"""

from __future__ import annotations

from typing import ClassVar

from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level, json_output=settings.groundwork_env != "development")
log = get_logger(__name__)


async def heartbeat(ctx: dict) -> None:
    """Proves the worker is alive and reaching Valkey."""
    log.info("worker_heartbeat", job_id=ctx.get("job_id"))


async def evaluate_achievements(ctx: dict, user_id: str) -> list[str]:
    """Re-read one learner's evidence and grant whatever it now supports.

    Takes a user id, never an achievement code: the job asks "what has this
    person earned", and the answer comes from graded answers and machine-checked
    lab results. There is no path here that grants something because a caller
    said so.
    """
    import uuid as _uuid

    from app.db.session import get_sessionmaker
    from app.models.identity import User
    from app.services.achievements import evaluate

    async with get_sessionmaker()() as session:
        user = await session.get(User, _uuid.UUID(user_id))
        if user is None:
            return []
        granted = await evaluate(session, user)
        return [item.code for item in granted]


async def startup(ctx: dict) -> None:
    log.info("worker_starting", environment=settings.groundwork_env)


async def shutdown(ctx: dict) -> None:
    log.info("worker_stopped")


class WorkerSettings:
    redis_settings = RedisSettings(host=settings.valkey_host, port=settings.valkey_port)
    # arq reads these off the class, so they are class-level by the library's design.
    functions: ClassVar[list] = [evaluate_achievements]
    cron_jobs: ClassVar[list] = [cron(heartbeat, minute=set(range(0, 60, 5)), run_at_startup=True)]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
