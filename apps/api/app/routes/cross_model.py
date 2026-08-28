"""Model-switch preview (V0.2)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Run
from app.schemas.cross_model import PreviewModelSwitchRequest, PreviewModelSwitchResponse
from app.services.cross_model import build_preview
from app.services.scope import Scope, resolve_scope

router = APIRouter(prefix="/runs", tags=["cross-model"])


@router.post(
    "/{run_id}/preview-model-switch", response_model=PreviewModelSwitchResponse
)
async def preview_model_switch(
    run_id: uuid.UUID,
    body: PreviewModelSwitchRequest,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> PreviewModelSwitchResponse:
    """What would carry over if this run's work were repeated on a different
    model, without actually executing anything (spec section 4)."""
    run = await session.get(Run, run_id)
    if run is None or run.project_id != scope.project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="run not found"
        )
    return await build_preview(session, scope, run_id, body.target_model)
