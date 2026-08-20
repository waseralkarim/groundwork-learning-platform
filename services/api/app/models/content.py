"""Content-domain models.

Content tables are a projection of `content/` in git. They hold no authoritative
state and can be rebuilt from scratch at any time — only the progress domain is
irreplaceable.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ContentVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One row per successful ingest of the content tree.

    Progress records reference the version a learner actually saw, so content can
    be revised without making historical results unexplainable.
    """

    __tablename__ = "content_versions"

    git_sha: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # server_default, not default: a Python-side default is invisible to
    # anything that inserts without going through the ORM, which eventually
    # something will.
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), index=True
    )
    topic_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # At most one current version, enforced by the database rather than by
        # remembering to do it in application code. Declared here as well as in
        # the migration, otherwise autogenerate proposes dropping it every run.
        Index(
            "uq_content_versions_single_current",
            "is_current",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ContentVersion {self.git_sha[:8]} current={self.is_current}>"
