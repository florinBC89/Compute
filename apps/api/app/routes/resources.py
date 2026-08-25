"""Resource endpoints (spec §33)."""

from __future__ import annotations

import datetime as _dt
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Resource
from app.schemas.resource import ResourceUpsertBody, ResourceUpsertResponse
from app.services.scope import Scope, resolve_scope

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("/upsert", response_model=ResourceUpsertResponse)
async def upsert(
    body: ResourceUpsertBody,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> ResourceUpsertResponse:
    """Record the current version of external state.

    ``changed`` tells the caller whether anything downstream can be reused, so
    an agent can skip a whole branch without computing a fingerprint first.
    """
    existing = (
        await session.execute(
            select(Resource).where(
                Resource.workspace_id == scope.workspace_id,
                Resource.project_id == scope.project_id,
                Resource.resource_key == body.resource_key,
            )
        )
    ).scalars().first()

    if existing is None:
        session.add(
            Resource(
                id=uuid.uuid4(),
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
                resource_key=body.resource_key,
                current_version=body.version,
                meta=body.metadata,
            )
        )
        return ResourceUpsertResponse(
            changed=True, previous_version=None, current_version=body.version
        )

    previous_version = existing.current_version
    existing.current_version = body.version
    existing.meta = body.metadata or existing.meta
    existing.updated_at = _dt.datetime.now(_dt.timezone.utc)

    return ResourceUpsertResponse(
        changed=previous_version != body.version,
        previous_version=previous_version,
        current_version=body.version,
    )
