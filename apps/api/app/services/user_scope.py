"""Map a verified Supabase session onto the app's workspace/project model
(V0.2 human-workspace slice).

The developer API-key path (``app.services.scope.resolve_scope``) and this
consumer Supabase-session path are fully parallel: both end in the same
``Scope`` dataclass, so every existing service (lookup, artifact_policy, the
metrics routes) works unmodified under either. The only new behavior here is
identity: on a user's first-ever verified request, exactly one workspace and
one owner membership are auto-provisioned for them (mirroring the shape of
``app.provision``'s idempotent-on-name workspace creation, but triggered by
login instead of an operator running it by hand).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Project, User, Workspace, WorkspaceMember
from app.services.scope import Scope
from app.services.supabase_auth import bearer_token, verify_supabase_jwt

__all__ = ["CurrentUser", "resolve_current_user", "resolve_user_scope"]


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    email: str
    workspace_id: uuid.UUID


async def _provision_workspace(session: AsyncSession, user: User) -> uuid.UUID:
    """First-login only: one workspace + one owner membership for this user."""
    workspace = Workspace(id=uuid.uuid4(), name=user.email)
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(
            id=uuid.uuid4(), workspace_id=workspace.id, user_id=user.id, role="owner"
        )
    )
    await session.flush()
    return workspace.id


async def _get_user_by_supabase_id(
    session: AsyncSession, supabase_user_id: str
) -> User | None:
    return (
        await session.execute(
            select(User).where(User.supabase_user_id == supabase_user_id)
        )
    ).scalars().first()


async def resolve_current_user(
    token: str = Depends(bearer_token),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    claims = verify_supabase_jwt(token)

    user = await _get_user_by_supabase_id(session, claims.supabase_user_id)
    first_login = user is None

    if first_login:
        user = User(
            id=uuid.uuid4(),
            supabase_user_id=claims.supabase_user_id,
            email=claims.email,
        )
        session.add(user)
        try:
            await session.flush()
        except IntegrityError:
            # Lost a race with a concurrent first-login request for the same
            # Supabase user (e.g. two authenticated requests firing on the
            # first page load) -- a UNIQUE violation here means the other
            # request's insert already committed (Postgres only raises the
            # conflict after the blocking transaction resolves), so its
            # user/workspace/membership are all there to find. Roll back our
            # own failed insert and use theirs instead of 500ing a user whose
            # login genuinely succeeded.
            await session.rollback()
            user = await _get_user_by_supabase_id(session, claims.supabase_user_id)
            if user is None:
                raise
            first_login = False

    if first_login:
        workspace_id = await _provision_workspace(session, user)
    else:
        membership = (
            await session.execute(
                select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
            )
        ).scalars().first()
        # Should always exist (created alongside the user above) -- if it's
        # somehow missing, re-provisioning is the correct recovery, not a
        # 500: an authenticated user must always land somewhere.
        workspace_id = (
            membership.workspace_id
            if membership is not None
            else await _provision_workspace(session, user)
        )

    return CurrentUser(user_id=user.id, email=user.email, workspace_id=workspace_id)


async def resolve_user_scope(
    x_computelayer_project: str | None = Header(default=None),
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> Scope:
    """``Scope`` for a Supabase-authenticated request -- a project must be
    named explicitly (a user has many), the same way a workspace-scoped API
    key requires ``X-ComputeLayer-Project`` in ``resolve_scope``.
    """
    if not x_computelayer_project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="an X-ComputeLayer-Project header is required",
        )

    project = (
        await session.execute(
            select(Project).where(
                Project.workspace_id == current_user.workspace_id,
                Project.slug == x_computelayer_project,
            )
        )
    ).scalars().first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown project {x_computelayer_project!r}",
        )

    return Scope(
        workspace_id=current_user.workspace_id,
        project_id=project.id,
        project_slug=project.slug,
        api_key_id=None,
    )
