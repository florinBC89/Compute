"""Human workspace: end-user identity + job orchestration (V0.2 slice).

Adds `users` and `workspace_members` (Supabase-backed end-user identity,
mapped onto the existing workspace/project model) and `jobs` + `job_events`
(orchestration state for one consumer-workspace research task -- deliberately
separate from `runs`, which stays the SDK's spec-defined compute-grouping).
All additive, no backfill: these tables are empty until the human-workspace
app starts writing to them.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("supabase_user_id", sa.Text(), nullable=False, unique=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_supabase_user_id", "users", ["supabase_user_id"])

    op.create_table(
        "workspace_members",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="owner"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("role IN ('owner')", name="ck_workspace_members_role"),
    )
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])
    op.create_index(
        "ux_workspace_members_workspace_user",
        "workspace_members",
        ["workspace_id", "user_id"],
        unique=True,
    )

    op.create_table(
        "jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("run_id", UUID, sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("task_text", sa.Text(), nullable=False),
        sa.Column("model_preference", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="QUEUED"),
        sa.Column("current_step", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cost_cap_usd", sa.Numeric(18, 8), nullable=False, server_default="0.50"),
        sa.Column("spent_usd", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_jobs_status",
        ),
    )
    op.create_index("ix_jobs_workspace_id", "jobs", ["workspace_id"])
    op.create_index("ix_jobs_project_id", "jobs", ["project_id"])
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_run_id", "jobs", ["run_id"])
    # The worker's dispatch query: oldest QUEUED job first.
    op.create_index(
        "idx_jobs_queued",
        "jobs",
        ["created_at"],
        postgresql_where=sa.text("status = 'QUEUED'"),
    )

    op.create_table(
        "job_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_job_events_job", "job_events", ["job_id", "id"])


def downgrade() -> None:
    op.drop_table("job_events")
    op.drop_table("jobs")
    op.drop_table("workspace_members")
    op.drop_table("users")
