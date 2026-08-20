"""The search index — a materialised projection of the *public* curriculum.

Two decisions worth stating, because both are easy to get wrong later.

**The index is built from public columns only.** Nothing here reads
`topic_items.solution`, `quiz_options.is_correct`, a lab's steps or its
solution. That is not a rule someone has to remember when adding a row type: the
builder in `app/content/search_index.py` takes the public payload and the
response model has no field for anything else, so leaking an answer through
search would require adding a column that does not exist.

**The tsvector is a generated column.** It cannot drift from the text it
describes, because Postgres recomputes it on every write. An index refreshed by
application code eventually disagrees with the content it indexes; one the
database maintains cannot.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Computed, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Title matches are worth more than body matches. Postgres weights are A to D and
# ts_rank applies its own multipliers; A over B is the whole ranking policy.
_TSV = (
    "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(body, '')), 'B')"
)


class ContentSearch(Base):
    __tablename__ = "content_search"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # topic | lesson | lab | exercise | troubleshooting | interview | assessment
    # | quiz | glossary
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)

    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=True, index=True
    )
    topic_slug: Mapped[str | None] = mapped_column(String(80), nullable=True)
    topic_title: Mapped[str | None] = mapped_column(String(160), nullable=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    # One line of context under the title in results — a section name, a lab
    # type, the term being defined.
    subtitle: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Where clicking the result takes the learner.
    url: Mapped[str] = mapped_column(String(300), nullable=False)
    # Orders results of equal rank so a topic outranks a lesson inside it.
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    tsv: Mapped[str] = mapped_column(TSVECTOR, Computed(text(_TSV), persisted=True))

    __table_args__ = (
        Index("ix_content_search_tsv", "tsv", postgresql_using="gin"),
        # Fuzzy title matching, so "capabilties" still finds capabilities. FTS
        # alone cannot do this — it matches lexemes, and a typo is not one.
        Index(
            "ix_content_search_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_content_search_entity_type", "entity_type"),
    )
