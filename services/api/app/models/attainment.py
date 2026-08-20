"""Achievements and certificates — what a learner has actually demonstrated.

The rule that shapes both tables: **nothing here is ever written from a request
body.** A client cannot claim an achievement or mint a certificate; it can only
ask the server to re-evaluate the evidence it already holds. That is why neither
model has a "grant" path taking a name or a score, and why the certificate's
verification code is generated here rather than supplied.

Certificates are gated on the competence model, not on completion. Clicking
through fifteen screens and passing a multiple-choice quiz is not proficiency,
and a certificate that says otherwise is worse than no certificate — it makes
every other one on the platform mean less.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserAchievement(Base):
    """One earned achievement.

    The rule definitions live in code (`app/services/achievements.py`), not in
    the database: they are logic, they change with the curriculum, and a rule
    engine configured through rows would be a worse version of a Python
    function that nobody could read.
    """

    __tablename__ = "user_achievements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuidv7()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Stable slug of the rule that granted it, e.g. "topic-mastered".
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    # What it was earned against — a topic slug, a course code. Empty for
    # achievements that are not scoped to one thing.
    scope: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # The evidence at the moment it was granted. Kept so that "why do I have
    # this?" has an answer a year later, when the rule may have changed.
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # Earning the same thing twice is not a thing. Re-evaluation is
        # idempotent because of this constraint, not because the code is careful.
        UniqueConstraint("user_id", "code", "scope", name="uq_user_achievements_identity"),
        Index("ix_user_achievements_user_earned", "user_id", "earned_at"),
    )


class Certificate(Base):
    """Issued for a course whose every objective has been demonstrated.

    Verifiable by a third party without an account: the code is the whole
    credential, and `/api/v1/certificates/{code}` returns who it was issued to
    and what it required. A certificate nobody can check is decoration.
    """

    __tablename__ = "certificates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuidv7()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    # Public, unguessable, and the only thing a verifier needs. Generated with
    # secrets.token_urlsafe — never derived from the user id, which would let
    # anyone enumerate certificates from a leaked id.
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # Denormalised on purpose: a certificate must still verify after the course
    # is retitled or the learner changes their display name. It is a statement
    # about a moment, not a live view.
    holder_name: Mapped[str] = mapped_column(String(120), nullable=False)
    course_title: Mapped[str] = mapped_column(String(160), nullable=False)
    course_code: Mapped[str] = mapped_column(String(8), nullable=False)
    topics_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # The weakest objective's score at issue time. Recorded because it is the
    # number the certificate actually attests to.
    weakest_objective_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_certificates_user_course"),)
