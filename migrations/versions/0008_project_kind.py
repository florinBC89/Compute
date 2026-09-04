"""Project kind (V0.3 Chat/Build toggle): projects.kind.

Distinguishes a "chat" conversation from a "build" one so the sidebar's
Recent list can show each tab its own set -- see components/Sidebar.tsx's
per-mode filtering and app.routes.jobs's create_job, which now threads
JobCreateRequest.project_kind through to a new project's kind at creation.
Existing rows default to "chat": nothing "build" existed before this.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("kind", sa.Text(), nullable=False, server_default="chat"),
    )
    op.create_check_constraint(
        "ck_projects_kind", "projects", "kind IN ('chat','build')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_projects_kind", "projects", type_="check")
    op.drop_column("projects", "kind")
