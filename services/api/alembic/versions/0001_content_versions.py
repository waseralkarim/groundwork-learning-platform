"""content_versions

Revision ID: 0001
Revises:
Created: 2026-08-15

The first table. Records one row per successful ingest of the content tree so a
learner's progress can be attributed to the content revision they actually saw.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("git_sha", sa.String(length=40), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("topic_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_versions")),
    )
    op.create_index(
        op.f("ix_content_versions_git_sha"), "content_versions", ["git_sha"], unique=False
    )
    op.create_index(
        op.f("ix_content_versions_is_current"), "content_versions", ["is_current"], unique=False
    )

    # At most one current version. Enforced by the database rather than by
    # remembering to do it in application code.
    op.create_index(
        "uq_content_versions_single_current",
        "content_versions",
        ["is_current"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index("uq_content_versions_single_current", table_name="content_versions")
    op.drop_index(op.f("ix_content_versions_is_current"), table_name="content_versions")
    op.drop_index(op.f("ix_content_versions_git_sha"), table_name="content_versions")
    op.drop_table("content_versions")
