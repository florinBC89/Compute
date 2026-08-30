"""Accs: persistent named agent identities (Agent OS V0.4 slice, "give Acc
a name and a face").

Additive, no backfill: empty until the workspace app starts creating Accs.
project_id is not unique -- a Project can hold multiple Accs.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "accs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_accs_workspace_id", "accs", ["workspace_id"])
    op.create_index("ix_accs_project_id", "accs", ["project_id"])


def downgrade() -> None:
    op.drop_table("accs")
