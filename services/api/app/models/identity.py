"""Identity and session models.

**Design revision, recorded deliberately.** The architecture doc specified a
short-lived JWT access token plus an opaque refresh token. Implementing it
against a server-rendered frontend made the cost clear: "hold the access token
in memory" has no meaning when React Server Components fetch on the server, and
the workarounds all end in putting the JWT in a cookie anyway — at which point
it is a session identifier with extra steps and worse revocation.

So: **opaque session tokens, stored hashed, in an httpOnly cookie.** A JWT buys
stateless verification, which is worth having when an auth service is separate
from many resource servers. Here the API and the database are one hop apart, and
what we actually want is instant revocation. Postgres gives us that; a JWT
actively fights it.

See docs/architecture/02-technology-stack.md §2.8.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuidv7()
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    # Argon2id. The parameters live with the hash, so raising them later does not
    # invalidate existing users — they are rehashed on their next login.
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'learner'"), default="learner"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.email}>"


class Session(Base):
    """A login session.

    The token itself is never stored — only its SHA-256 hash. Read access to
    this table therefore does not let anyone mint a session, which is the same
    reasoning that applies to password hashes.
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuidv7()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Sliding window: refreshed on use, but never beyond absolute_expires_at.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (Index("ix_sessions_expires_at", "expires_at"),)


class LoginAttempt(Base):
    """Rate-limiting ledger.

    Recorded per email *and* per IP. Limiting only by IP lets a botnet spread an
    attack across addresses; limiting only by email lets one attacker lock out
    every account they know of.
    """

    __tablename__ = "login_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuidv7()
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_login_attempts_email_at", "email", "at"),)


class AuditLog(Base):
    """Append-only record of security-relevant actions.

    Cheap now, unfakeable later. Adding it after an incident is too late.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuidv7()
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_audit_log_actor_at", "actor_id", "at"),)


class UserProgress(Base, TimestampMixin):
    """The central progress table.

    Deliberately generic rather than one table per content type: the dashboard,
    the roadmap and every prerequisite check need "everything this user has
    done" in a single query, and nine unions on the hottest read path would be
    a poor trade for one foreign key.

    `entity_id` is a deterministic content UUID, so it survives content churn.
    See docs/architecture/05-data-model.md §5.4.
    """

    __tablename__ = "user_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuidv7()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # server_default, not default: a Python-side default is not applied until
    # flush, so reading the attribute before then gives None — and `None += 1`
    # is a runtime error rather than a type error.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'in_progress'")
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), default=0
    )
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_user_progress_identity"),
        Index("ix_user_progress_user_type_status", "user_id", "entity_type", "status"),
    )


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuidv7()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    content_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_versions.id", ondelete="SET NULL"), nullable=True
    )

    answers: Mapped[list[QuizAnswer]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class QuizAnswer(Base):
    """One answer within an attempt.

    Stored per question rather than as a blob so per-objective weakness analysis
    is a query rather than a migration.
    """

    __tablename__ = "quiz_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuidv7()
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False
    )
    given: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )

    attempt: Mapped[QuizAttempt] = relationship(back_populates="answers")

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_quiz_answers_attempt_question"),
    )


class Hypothesis(Base):
    """A learner's diagnosis, submitted before the solution is revealed.

    This row is the gate. `reveal_policy: progressive` scenarios refuse to serve
    their root cause until one exists — which is the whole pedagogical point,
    and the thing every troubleshooting tutorial on the internet gets wrong.
    """

    __tablename__ = "hypotheses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuidv7()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topic_items.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Filled in after the reveal: did the learner think they got it right?
    self_assessment: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (Index("ix_hypotheses_user_item", "user_id", "item_id"),)
