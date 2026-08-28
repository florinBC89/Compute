"""Cross-model reuse portability policy resolution (V0.2).

Resolution order: a project-level override, then a workspace-level default,
then :data:`computelayer.semantics.DEFAULT_PORTABLE_ARTIFACT_TYPES` (the same
fallback :class:`~computelayer.testing.LocalBackend` uses, since it has no
policy store of its own). This module is the only place that queries
``artifact_type_policies`` -- ``packages/python-sdk/computelayer/semantics.py``
stays free of DB access so it can keep being shared, unmodified, between this
API and the in-memory reference backend.
"""

from __future__ import annotations

import uuid

from computelayer.semantics import DEFAULT_PORTABLE_ARTIFACT_TYPES
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArtifactTypePolicy
from app.models.computation import ARTIFACT_TYPES
from app.services.scope import Scope

__all__ = ["resolve_portability", "list_effective_policies", "upsert_policy"]


async def resolve_portability(
    session: AsyncSession,
    scope: Scope,
    artifact_type: str | None,
) -> bool:
    if artifact_type is None:
        return False

    project_row = (
        await session.execute(
            select(ArtifactTypePolicy).where(
                ArtifactTypePolicy.workspace_id == scope.workspace_id,
                ArtifactTypePolicy.project_id == scope.project_id,
                ArtifactTypePolicy.artifact_type == artifact_type,
            )
        )
    ).scalars().first()
    if project_row is not None:
        return bool(project_row.portable)

    workspace_row = (
        await session.execute(
            select(ArtifactTypePolicy).where(
                ArtifactTypePolicy.workspace_id == scope.workspace_id,
                ArtifactTypePolicy.project_id.is_(None),
                ArtifactTypePolicy.artifact_type == artifact_type,
            )
        )
    ).scalars().first()
    if workspace_row is not None:
        return bool(workspace_row.portable)

    return artifact_type in DEFAULT_PORTABLE_ARTIFACT_TYPES


async def list_effective_policies(
    session: AsyncSession, scope: Scope
) -> list[dict[str, object]]:
    """The effective (artifact_type, portable, source) for all seven types.

    "source" tells the caller *why* -- a project override, a workspace
    default, or the hardcoded fallback -- which is what a settings UI needs
    to show without a second round trip.
    """
    project_rows = {
        row.artifact_type: row
        for row in (
            await session.execute(
                select(ArtifactTypePolicy).where(
                    ArtifactTypePolicy.workspace_id == scope.workspace_id,
                    ArtifactTypePolicy.project_id == scope.project_id,
                )
            )
        )
        .scalars()
        .all()
    }
    workspace_rows = {
        row.artifact_type: row
        for row in (
            await session.execute(
                select(ArtifactTypePolicy).where(
                    ArtifactTypePolicy.workspace_id == scope.workspace_id,
                    ArtifactTypePolicy.project_id.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }

    entries: list[dict[str, object]] = []
    for artifact_type in ARTIFACT_TYPES:
        if artifact_type in project_rows:
            entries.append(
                {
                    "artifact_type": artifact_type,
                    "portable": bool(project_rows[artifact_type].portable),
                    "source": "project",
                }
            )
        elif artifact_type in workspace_rows:
            entries.append(
                {
                    "artifact_type": artifact_type,
                    "portable": bool(workspace_rows[artifact_type].portable),
                    "source": "workspace",
                }
            )
        else:
            entries.append(
                {
                    "artifact_type": artifact_type,
                    "portable": artifact_type in DEFAULT_PORTABLE_ARTIFACT_TYPES,
                    "source": "default",
                }
            )
    return entries


async def upsert_policy(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    artifact_type: str,
    portable: bool,
) -> ArtifactTypePolicy:
    """Insert or update the policy row for one (workspace, project, type)."""
    existing = (
        await session.execute(
            select(ArtifactTypePolicy).where(
                ArtifactTypePolicy.workspace_id == workspace_id,
                ArtifactTypePolicy.project_id == project_id
                if project_id is not None
                else ArtifactTypePolicy.project_id.is_(None),
                ArtifactTypePolicy.artifact_type == artifact_type,
            )
        )
    ).scalars().first()
    if existing is not None:
        existing.portable = portable
        await session.flush()
        return existing

    row = ArtifactTypePolicy(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        artifact_type=artifact_type,
        portable=portable,
    )
    session.add(row)
    await session.flush()
    return row
