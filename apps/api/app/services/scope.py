"""Authentication and request scoping (spec §28, §56).

Every request is scoped to one workspace and one project.  API keys are stored
as SHA-256 digests; the plaintext exists only at creation time.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ApiKey, Project

KEY_PREFIX_LENGTH = 12


@dataclass(frozen=True)
class Scope:
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    project_slug: str
    api_key_id: uuid.UUID


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_api_key(environment: str = "live") -> str:
    return f"cl_{environment}_{secrets.token_urlsafe(32)}"


async def resolve_scope(
    authorization: str | None = Header(default=None),
    x_computelayer_project: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Scope:
    """Resolve ``Authorization: Bearer cl_live_xxx`` to a workspace + project."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    plaintext = authorization.split(" ", 1)[1].strip()
    record = (
        await session.execute(
            select(ApiKey).where(
                ApiKey.key_hash == hash_api_key(plaintext),
                ApiKey.active.is_(True),
            )
        )
    ).scalars().first()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key"
        )

    project_id = record.project_id
    project_slug = ""

    if project_id is None:
        # Workspace-scoped key: the project must come from the request.
        if not x_computelayer_project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="workspace-scoped key requires an X-ComputeLayer-Project header",
            )
        project = (
            await session.execute(
                select(Project).where(
                    Project.workspace_id == record.workspace_id,
                    Project.slug == x_computelayer_project,
                )
            )
        ).scalars().first()
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"unknown project {x_computelayer_project!r}",
            )
        project_id, project_slug = project.id, project.slug
    else:
        project = await session.get(Project, project_id)
        project_slug = project.slug if project else ""

    return Scope(
        workspace_id=record.workspace_id,
        project_id=project_id,
        project_slug=project_slug,
        api_key_id=record.id,
    )
