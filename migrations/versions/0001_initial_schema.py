"""Initial ComputeLayer V0.1 schema (spec §6).

Revision ID: 0001
Revises:
Create Date: 2026-08-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "projects",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("workspace_id", "slug"),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])
    op.create_index("ix_api_keys_workspace_id", "api_keys", ["workspace_id"])
    op.create_index("ix_api_keys_project_id", "api_keys", ["project_id"])

    op.create_table(
        "runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("external_run_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "total_input_tokens", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_output_tokens", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "estimated_cost_usd",
            sa.Numeric(18, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "estimated_saved_usd",
            sa.Numeric(18, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED')", name="ck_runs_status"
        ),
    )
    op.create_index("ix_runs_workspace_id", "runs", ["workspace_id"])
    op.create_index("ix_runs_project_id", "runs", ["project_id"])

    op.create_table(
        "computations",
        sa.Column("id", UUID, primary_key=True),
        # Monotonic insertion order. "Newest valid computation" is resolved by
        # this rather than created_at, which defaults to now() -- transaction
        # time -- and therefore ties for rows written in one transaction.
        sa.Column("seq", sa.BigInteger(), sa.Identity(), nullable=False, unique=True),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("run_id", UUID, sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("logical_key", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("cache_status", sa.Text(), nullable=False),
        sa.Column("input_json", JSONB, nullable=True),
        sa.Column("output_json", JSONB, nullable=True),
        sa.Column("output_hash", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("prompt_hash", sa.Text(), nullable=True),
        sa.Column("tool_schema_hash", sa.Text(), nullable=True),
        sa.Column("code_version", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("saved_usd", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.BigInteger(), nullable=True),
        sa.Column("ttl_seconds", sa.BigInteger(), nullable=True),
        sa.Column("reusable", sa.Boolean(), nullable=False, server_default=sa.true()),
        # Set on HIT observation rows: the computation whose output was reused.
        # A real column rather than a metadata key, so "tokens avoided" is an
        # indexed join instead of a cast out of JSONB.
        sa.Column(
            "reused_from", UUID, sa.ForeignKey("computations.id"), nullable=True
        ),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED')", name="ck_computations_status"
        ),
        sa.CheckConstraint(
            "cache_status IN ('HIT','MISS','STALE','FORCED')",
            name="ck_computations_cache_status",
        ),
        # §6.4 specifies CHAR(64) for the digest columns. CHAR does not enforce
        # a hex digest, and PostgreSQL casts bpchar to text when it is compared
        # against a text parameter -- which makes the column's own index
        # unusable from the driver. TEXT plus a format check gives the real
        # guarantee and keeps the indexes usable.
        sa.CheckConstraint(
            "fingerprint ~ '^[0-9a-f]{64}$'", name="ck_computations_fingerprint_hex"
        ),
        sa.CheckConstraint(
            "logical_key ~ '^[0-9a-f]{64}$'", name="ck_computations_logical_key_hex"
        ),
        sa.CheckConstraint(
            "output_hash IS NULL OR output_hash ~ '^[0-9a-f]{64}$'",
            name="ck_computations_output_hash_hex",
        ),
    )
    op.create_index(
        "idx_computations_fingerprint",
        "computations",
        ["workspace_id", "project_id", "fingerprint"],
    )
    op.create_index(
        "idx_computations_logical_key",
        "computations",
        ["workspace_id", "project_id", "logical_key"],
    )
    op.create_index("idx_computations_run", "computations", ["run_id"])
    op.create_index("idx_computations_reused_from", "computations", ["reused_from"])
    op.create_index(
        "idx_computations_created", "computations", [sa.text("created_at DESC")]
    )
    # Partial indexes covering exactly the rows each lookup may return, so the
    # §58 latency target does not degrade as history accumulates. Measured over
    # 50k rows: 0.08 ms indexed vs 12.8 ms sequential.
    #
    # Queries must spell the predicate ``reusable = TRUE``. PostgreSQL will not
    # prove that ``reusable IS TRUE`` implies it, and silently falls back to a
    # sequential scan if you write it that way.
    op.create_index(
        "idx_computations_reusable",
        "computations",
        ["workspace_id", "project_id", "fingerprint", sa.text("seq DESC")],
        postgresql_where=sa.text("status = 'SUCCEEDED' AND reusable = TRUE"),
    )
    op.create_index(
        "idx_computations_logical_reusable",
        "computations",
        ["workspace_id", "project_id", "logical_key", sa.text("seq DESC")],
        postgresql_where=sa.text("status = 'SUCCEEDED'"),
    )

    op.create_table(
        "computation_dependencies",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "computation_id",
            UUID,
            sa.ForeignKey("computations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dependency_key", sa.Text(), nullable=False),
        sa.Column("dependency_version", sa.Text(), nullable=False),
        sa.Column(
            "dependency_type",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'EXTERNAL'"),
        ),
        sa.Column(
            "source_computation_id", UUID, sa.ForeignKey("computations.id"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("computation_id", "dependency_key"),
        sa.CheckConstraint(
            "dependency_type IN "
            "('EXTERNAL','COMPUTATION','FILE','API','DATABASE','MANUAL')",
            name="ck_dependency_type",
        ),
    )
    op.create_index(
        "idx_dependencies_key",
        "computation_dependencies",
        ["dependency_key", "dependency_version"],
    )
    op.create_index(
        "idx_dependencies_source",
        "computation_dependencies",
        ["source_computation_id"],
    )

    op.create_table(
        "resources",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("resource_key", sa.Text(), nullable=False),
        sa.Column("current_version", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("workspace_id", "project_id", "resource_key"),
    )

    op.create_table(
        "computation_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "computation_id",
            UUID,
            sa.ForeignKey("computations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_events_computation", "computation_events", ["computation_id", "id"]
    )


def downgrade() -> None:
    op.drop_table("computation_events")
    op.drop_table("resources")
    op.drop_table("computation_dependencies")
    op.drop_table("computations")
    op.drop_table("runs")
    op.drop_table("api_keys")
    op.drop_table("projects")
    op.drop_table("workspaces")
