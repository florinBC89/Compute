"""Cross-model reuse portability policy endpoints (V0.2).

Unlike a path-parameterized ``/workspaces/{id}/...``, every route in this API
is already scoped to one workspace + project via the authenticated API key
(``Depends(resolve_scope)``) -- these routes follow that same convention.
Whether an update applies workspace-wide or just to the current project is
expressed by the request body's ``scope`` field, not the URL.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.artifact_policy import (
    ArtifactPolicyListResponse,
    ArtifactPolicyUpdateRequest,
)
from app.schemas.computation import ArtifactType
from app.services.artifact_policy import list_effective_policies, upsert_policy
from app.services.scope import Scope, resolve_scope

router = APIRouter(prefix="/artifact-policies", tags=["artifact-policies"])


@router.get("", response_model=ArtifactPolicyListResponse)
async def list_policies(
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> ArtifactPolicyListResponse:
    """The effective portability policy for all seven artifact types."""
    return ArtifactPolicyListResponse(
        policies=await list_effective_policies(session, scope)
    )


@router.put("/{artifact_type}", response_model=ArtifactPolicyListResponse)
async def update_policy(
    artifact_type: ArtifactType,
    body: ArtifactPolicyUpdateRequest,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> ArtifactPolicyListResponse:
    """Set whether one artifact type is treated as portable across models."""
    await upsert_policy(
        session,
        workspace_id=scope.workspace_id,
        project_id=scope.project_id if body.scope == "project" else None,
        artifact_type=artifact_type,
        portable=body.portable,
    )
    return ArtifactPolicyListResponse(
        policies=await list_effective_policies(session, scope)
    )
