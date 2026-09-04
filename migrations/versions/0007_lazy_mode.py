"""Lazy mode (V0.3 chat): jobs.lazy_mode.

A per-turn opt-in that appends a code-minimalism ruleset to that turn's
system prompt (see app.agent.chat.LAZY_MODE_SYSTEM_SUFFIX) -- off by
default, set once at job creation and never changed after, same lifecycle
as model_preference.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("lazy_mode", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("jobs", "lazy_mode")
