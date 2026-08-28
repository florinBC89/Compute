"""Cross-model reuse: artifact typing + portability policy (V0.2 slice).

Adds three nullable columns to `computations` -- model_agnostic_fingerprint,
artifact_type, reuse_kind -- and a new `artifact_type_policies` table for the
per-workspace/per-project portability policy. All additive, no backfill: rows
written before this migration are simply unclassified and ineligible as
cross-model sources, which is correct (not a gap) since cross-model reuse
only ever applies going forward.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)

ARTIFACT_TYPES = (
    "source",
    "fact",
    "structured_data",
    "research_note",
    "analysis",
    "draft",
    "citation",
)


def upgrade() -> None:
    op.add_column(
        "computations",
        sa.Column("model_agnostic_fingerprint", sa.Text(), nullable=True),
    )
    op.add_column(
        "computations", sa.Column("artifact_type", sa.Text(), nullable=True)
    )
    op.add_column("computations", sa.Column("reuse_kind", sa.Text(), nullable=True))

    op.create_check_constraint(
        "ck_computations_model_agnostic_fingerprint_hex",
        "computations",
        "model_agnostic_fingerprint IS NULL OR "
        "model_agnostic_fingerprint ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        "ck_computations_artifact_type",
        "computations",
        "artifact_type IS NULL OR artifact_type IN ("
        + ",".join(f"'{value}'" for value in ARTIFACT_TYPES)
        + ")",
    )
    op.create_check_constraint(
        "ck_computations_reuse_kind",
        "computations",
        "reuse_kind IS NULL OR reuse_kind IN ('CROSS_MODEL')",
    )

    op.create_table(
        "artifact_type_policies",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id"), nullable=False),
        # NULL = workspace-wide default; set = override for that project.
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("portable", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint(
            "artifact_type IN ("
            + ",".join(f"'{value}'" for value in ARTIFACT_TYPES)
            + ")",
            name="ck_artifact_policy_type",
        ),
    )
    op.create_index("ix_artifact_type_policies_workspace_id", "artifact_type_policies", ["workspace_id"])
    op.create_index("ix_artifact_type_policies_project_id", "artifact_type_policies", ["project_id"])
    # Two partial unique indexes rather than one UniqueConstraint: NULL is
    # never equal to NULL in SQL, so a plain UNIQUE(workspace_id, project_id,
    # artifact_type) would let unlimited duplicate workspace-default rows
    # (project_id IS NULL) through.
    op.create_index(
        "ux_artifact_policy_workspace_default",
        "artifact_type_policies",
        ["workspace_id", "artifact_type"],
        unique=True,
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.create_index(
        "ux_artifact_policy_project_override",
        "artifact_type_policies",
        ["workspace_id", "project_id", "artifact_type"],
        unique=True,
        postgresql_where=sa.text("project_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("artifact_type_policies")
    op.drop_constraint("ck_computations_reuse_kind", "computations", type_="check")
    op.drop_constraint("ck_computations_artifact_type", "computations", type_="check")
    op.drop_constraint(
        "ck_computations_model_agnostic_fingerprint_hex", "computations", type_="check"
    )
    op.drop_column("computations", "reuse_kind")
    op.drop_column("computations", "artifact_type")
    op.drop_column("computations", "model_agnostic_fingerprint")
