"""Current-user identity (V0.2 human-workspace slice).

First endpoint exercising the Supabase-session path end to end -- proves
JWT verification, first-login workspace auto-provisioning, and idempotency
on a repeat call, before any workspace-app frontend exists.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Project, Workspace
from app.schemas.user import MeResponse, ProjectSummary
from app.services.user_scope import CurrentUser, resolve_current_user

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    workspace = await session.get(Workspace, current_user.workspace_id)
    projects = (
        await session.execute(
            select(Project)
            .where(Project.workspace_id == current_user.workspace_id)
            .order_by(Project.created_at.desc())
        )
    ).scalars().all()

    return MeResponse(
        user_id=str(current_user.user_id),
        email=current_user.email,
        workspace_id=str(current_user.workspace_id),
        workspace_name=workspace.name if workspace else "",
        projects=[
            ProjectSummary(id=str(p.id), name=p.name, slug=p.slug) for p in projects
        ],
    )
