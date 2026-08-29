"""Chat turns (V0.3 slice): jobs.answer_text.

Adds the clean assistant-facing answer text to `jobs`, distinct from the
internal step artifacts it's built from -- what apps/workspace's chat
thread will render as a turn's reply. No new table: per the V0.3 plan's
"Job-as-turn" simplification, a chat turn is modeled as what `jobs`
already almost is (`task_text` is already the user's ask), avoiding a
second, parallel conversation/message schema. A project's turn history is
just its jobs ordered by `created_at`.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("answer_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "answer_text")
