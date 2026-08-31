"""Rename accs -> ethicals (Agent OS V0.4 slice renamed: "give Ethical a
name and a face").

Table rename only -- the shape from 0005 is unchanged, and the table was
never live-populated (no successful create predates this migration), so
this is a plain rename with no data migration needed. Postgres doesn't
rename indexes along with their table, so those are renamed explicitly to
keep them matching what a fresh create_table would have named them.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-31
"""

from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("accs", "ethicals")
    op.execute("ALTER INDEX ix_accs_workspace_id RENAME TO ix_ethicals_workspace_id")
    op.execute("ALTER INDEX ix_accs_project_id RENAME TO ix_ethicals_project_id")


def downgrade() -> None:
    op.execute("ALTER INDEX ix_ethicals_workspace_id RENAME TO ix_accs_workspace_id")
    op.execute("ALTER INDEX ix_ethicals_project_id RENAME TO ix_accs_project_id")
    op.rename_table("ethicals", "accs")
