"""Cross-model reuse portability policy (V0.2).

Whether an artifact type (source, fact, structured_data, research_note,
analysis, draft, citation) survives a model switch is configurable per
workspace, with an optional per-project override -- a `project_id IS NULL`
row is the workspace-wide default; a `project_id IS NOT NULL` row overrides
it for that project. Resolution order (see app.services.artifact_policy) is
project row -> workspace row -> hardcoded fallback default.
"""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_fk, uuid_pk
from app.models.computation import ARTIFACT_TYPES


class ArtifactTypePolicy(Base):
    __tablename__ = "artifact_type_policies"
    __table_args__ = (
        CheckConstraint(
            "artifact_type IN ("
            + ",".join(f"'{value}'" for value in ARTIFACT_TYPES)
            + ")",
            name="ck_artifact_policy_type",
        ),
        # NULL is never equal to NULL, so a plain UniqueConstraint on
        # (workspace_id, project_id, artifact_type) would let unlimited
        # duplicate workspace-default rows (project_id IS NULL) through.
        # Two partial unique indexes instead: one per "scope."
        Index(
            "ux_artifact_policy_workspace_default",
            "workspace_id",
            "artifact_type",
            unique=True,
            postgresql_where=text("project_id IS NULL"),
        ),
        Index(
            "ux_artifact_policy_project_override",
            "workspace_id",
            "project_id",
            "artifact_type",
            unique=True,
            postgresql_where=text("project_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = uuid_fk("workspaces.id")
    project_id: Mapped[uuid.UUID | None] = uuid_fk("projects.id", nullable=True)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    portable: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
