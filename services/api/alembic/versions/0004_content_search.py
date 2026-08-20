"""content search index

Revision ID: 0004
Revises: 0003
Created: 2026-08-15 10:41:02.117430
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Weighted so a title match outranks a body match. Kept identical to the
# expression in app/models/search.py — if they diverge, Alembic autogenerate
# will report the table as changed on the next revision, which is the intended
# alarm.
TSV = (
    "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(body, '')), 'B')"
)


def upgrade() -> None:
    # Fuzzy title matching needs trigrams. Postgres ships it; this only enables
    # it in this database.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "content_search",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("topic_slug", sa.String(length=80), nullable=True),
        sa.Column("topic_title", sa.String(length=160), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("subtitle", sa.String(length=300), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=300), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("tsv", postgresql.TSVECTOR(), sa.Computed(TSV, persisted=True), nullable=True),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_search_topic_id", "content_search", ["topic_id"])
    op.create_index("ix_content_search_entity_type", "content_search", ["entity_type"])
    op.create_index(
        "ix_content_search_tsv", "content_search", ["tsv"], postgresql_using="gin"
    )
    op.create_index(
        "ix_content_search_title_trgm",
        "content_search",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_content_search_title_trgm", table_name="content_search")
    op.drop_index("ix_content_search_tsv", table_name="content_search")
    op.drop_index("ix_content_search_entity_type", table_name="content_search")
    op.drop_index("ix_content_search_topic_id", table_name="content_search")
    op.drop_table("content_search")
