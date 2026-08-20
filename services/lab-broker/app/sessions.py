"""Lab session lifecycle.

Owns the rules a learner cannot see: how many labs one person may run at once,
how long a lab lives, and what happens to a lab whose owner closed the tab.

The TTL is the load-bearing one. A lab that only dies when the learner ends it
does not die, because nobody ends anything — they close the tab. Every session
carries a hard expiry and a reaper enforces it from outside, so the worst case
for a forgotten lab is one TTL of wasted memory rather than a container running
until the host is rebooted.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.core.logging import get_logger
from app.core.telemetry import record_session_ended
from app.provisioner import LabHandle, LabSpec, Provisioner

log = get_logger(__name__)

# One lab at a time per learner. Two labs is rarely a real need and always a
# quick way to exhaust a workstation.
MAX_ACTIVE_SESSIONS_PER_USER = 1
MAX_ACTIVE_SESSIONS_TOTAL = 8
DEFAULT_TTL = timedelta(minutes=45)
MAX_TTL = timedelta(minutes=120)
REAPER_INTERVAL_SECONDS = 20


class SessionError(Exception):
    pass


class QuotaExceededError(SessionError):
    pass


class SessionNotFoundError(SessionError):
    pass


@dataclass
class LabSession:
    id: uuid.UUID
    user_id: str
    lab_id: str
    topic_slug: str
    handle: LabHandle
    spec: LabSpec
    created_at: datetime
    expires_at: datetime
    step_results: dict[str, list[dict]] = field(default_factory=dict)
    destroyed: bool = False

    @property
    def seconds_remaining(self) -> int:
        return max(0, int((self.expires_at - datetime.now(UTC)).total_seconds()))

    @property
    def expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at


class SessionManager:
    def __init__(self, provisioner: Provisioner) -> None:
        self.provisioner = provisioner
        self._sessions: dict[uuid.UUID, LabSession] = {}
        self._lock = asyncio.Lock()
        self._reaper: asyncio.Task | None = None

    # ------------------------------------------------------------------ create

    async def create(
        self, *, user_id: str, lab_id: str, topic_slug: str, spec: LabSpec
    ) -> LabSession:
        async with self._lock:
            mine = [s for s in self._sessions.values() if s.user_id == user_id and not s.destroyed]
            if len(mine) >= MAX_ACTIVE_SESSIONS_PER_USER:
                raise QuotaExceededError(
                    "You already have a lab running. End it before starting another — "
                    f"({mine[0].lab_id}, {mine[0].seconds_remaining // 60} minutes left)."
                )
            active = sum(1 for s in self._sessions.values() if not s.destroyed)
            if active >= MAX_ACTIVE_SESSIONS_TOTAL:
                raise QuotaExceededError("The lab host is at capacity. Try again in a few minutes.")

        session_id = uuid.uuid4()
        handle = await self.provisioner.create(spec, session_id)

        ttl = min(timedelta(minutes=spec.duration_minutes * 2), MAX_TTL) or DEFAULT_TTL
        now = datetime.now(UTC)
        session = LabSession(
            id=session_id,
            user_id=user_id,
            lab_id=lab_id,
            topic_slug=topic_slug,
            handle=handle,
            spec=spec,
            created_at=now,
            expires_at=now + ttl,
        )

        async with self._lock:
            self._sessions[session_id] = session

        log.info(
            "lab_session_created",
            session_id=str(session_id),
            user_id=user_id,
            lab_id=lab_id,
            ttl_minutes=int(ttl.total_seconds() // 60),
        )
        return session

    # -------------------------------------------------------------------- read

    def get(self, session_id: uuid.UUID, user_id: str) -> LabSession:
        session = self._sessions.get(session_id)
        # Same error for "not yours" and "does not exist", so session ids are
        # not enumerable.
        if session is None or session.destroyed or session.user_id != user_id:
            raise SessionNotFoundError("lab session not found")
        if session.expired:
            raise SessionNotFoundError("this lab session has expired")
        return session

    def for_user(self, user_id: str) -> list[LabSession]:
        return [s for s in self._sessions.values() if s.user_id == user_id and not s.destroyed]

    @property
    def active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if not s.destroyed)

    # ----------------------------------------------------------------- destroy

    async def destroy(self, session_id: uuid.UUID, *, reason: str = "ended") -> None:
        session = self._sessions.get(session_id)
        if session is None or session.destroyed:
            return
        session.destroyed = True
        await self.provisioner.destroy(session.handle)
        async with self._lock:
            self._sessions.pop(session_id, None)
        lived = (datetime.now(UTC) - session.created_at).total_seconds()
        # Sessions that consistently hit the TTL mean the limit is too short for
        # the lab; sessions that end in seconds mean something is broken at the
        # start. The reason label is what separates those two stories.
        record_session_ended(lived, session.lab_id, reason)
        log.info(
            "lab_session_destroyed",
            session_id=str(session_id),
            reason=reason,
            lived_seconds=int(lived),
        )

    # ------------------------------------------------------------------ reaper

    async def reap_once(self) -> int:
        expired = [s.id for s in list(self._sessions.values()) if s.expired and not s.destroyed]
        for session_id in expired:
            await self.destroy(session_id, reason="ttl_expired")
        return len(expired)

    async def _reaper_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(REAPER_INTERVAL_SECONDS)
                await self.reap_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("reaper_iteration_failed")

    def start_reaper(self) -> None:
        if self._reaper is None or self._reaper.done():
            self._reaper = asyncio.create_task(self._reaper_loop())

    async def shutdown(self) -> None:
        """Destroy every lab on the way out.

        Without this, restarting the broker orphans every running container.
        `sweep_orphans` is the backstop for an unclean exit; this is the clean one.
        """
        if self._reaper is not None:
            self._reaper.cancel()
        for session_id in list(self._sessions):
            await self.destroy(session_id, reason="broker_shutdown")

    def known_session_ids(self) -> set[str]:
        return {str(s.id) for s in self._sessions.values() if not s.destroyed}
