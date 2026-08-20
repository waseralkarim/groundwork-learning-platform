"""Projects and their self-reviews.

A project is the only thing on this platform the machine cannot mark. What it
produces — a repository, a running system, a written design — is outside the
platform, and pretending to grade it would be worse than admitting it cannot.

So the rubric is a structure for honest self-review, and the design leans into
that rather than around it:

- Every criterion demands **evidence**: a file, a command, a line of output the
  learner points at. A score with no evidence is an opinion, and the API rejects
  it.
- Scores are recorded but never contribute to competence or a certificate.
  Self-assessment that unlocks something stops being self-assessment.
- Submissions are versioned by keeping every one rather than overwriting, so a
  learner can see how their own judgement changed on a second attempt.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Project(Base):
    """Projected from `content/projects/*.yaml`, keyed deterministically."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    content_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    level: Mapped[str] = mapped_column(String(2), nullable=False)
    estimated_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    # Content ids of the topics this project draws on. Stored as ids rather than
    # foreign keys because a project may reference a topic that has not been
    # written yet, and refusing to load it would block the project on content
    # that is scheduled rather than missing.
    requires_topics: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    constraints: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    deliverables: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rubric: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    going_further: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class ProjectSubmission(Base):
    """One self-review of one attempt.

    Kept, not replaced. A second submission is a new row, which is what lets a
    learner compare their own judgement across attempts — usually the most
    valuable thing a project produces.
    """

    __tablename__ = "project_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuidv7()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Where the work lives. Never fetched by the platform — see the API module
    # for why a server that follows learner-supplied URLs is a liability.
    artifact_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # [{criterion_id, score, evidence}] — evidence required, enforced at the API.
    scores: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # The learner's own weighted total. Recorded for their reference and used for
    # nothing else: it is deliberately not an input to competence.
    self_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_project_submissions_user_project", "user_id", "project_id", "submitted_at"),
    )
