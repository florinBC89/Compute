"""Model-switch preview (V0.2)."""

from __future__ import annotations

import uuid

from computelayer.semantics import is_reusable
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Computation, Run
from app.schemas.cross_model import (
    PreviewItem,
    PreviewModelSwitchRequest,
    PreviewModelSwitchResponse,
)
from app.services.artifact_policy import resolve_portability
from app.services.lookup import find_previous, to_stored
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
    model, without actually executing anything (spec section 4).

    Pure read: no lookup/start/complete calls, no stampede lock, no new
    computation rows. For every distinct logical key this run produced, the
    *current* best candidate for that key -- project-wide, not just this run,
    matching how a real lookup resolves it -- is evaluated against the same
    portability policy the real cross-model lookup path uses.
    """
    run = await session.get(Run, run_id)
    if run is None or run.project_id != scope.project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="run not found"
        )

    rows = (
        await session.execute(
            select(Computation)
            .where(
                Computation.run_id == run_id,
                Computation.status == "SUCCEEDED",
            )
            .order_by(Computation.created_at)
        )
    ).scalars().all()

    seen: set[str] = set()
    items: list[PreviewItem] = []
    estimated_incremental_cost = 0.0

    for row in rows:
        if row.logical_key in seen:
            continue
        seen.add(row.logical_key)

        previous = await find_previous(session, scope, row.logical_key)
        item = await _evaluate(session, scope, row.name, row.logical_key, previous, body.target_model)
        items.append(item)
        if item.decision == "RECOMPUTE":
            estimated_incremental_cost += item.cost_if_recomputed_usd

    reusable_count = sum(1 for item in items if item.decision == "REUSE")
    return PreviewModelSwitchResponse(
        target_model=body.target_model,
        items=items,
        reusable_count=reusable_count,
        recompute_count=len(items) - reusable_count,
        estimated_incremental_cost_usd=round(estimated_incremental_cost, 8),
    )


async def _evaluate(
    session: AsyncSession,
    scope: Scope,
    name: str,
    logical_key: str,
    previous: Computation | None,
    target_model: str,
) -> PreviewItem:
    if previous is None:
        return PreviewItem(
            name=name,
            logical_key=logical_key,
            decision="RECOMPUTE",
            reason="no successful computation exists for this logical key",
        )

    base = PreviewItem(
        name=name,
        logical_key=logical_key,
        decision="RECOMPUTE",
        reason="",
        artifact_type=previous.artifact_type,
        current_model=previous.model,
        cost_if_recomputed_usd=float(previous.cost_usd or 0),
    )

    if previous.model == target_model:
        base.decision = "REUSE"
        base.reason = "already ran on the target model"
        base.cost_if_recomputed_usd = 0.0
        return base

    if previous.artifact_type is None:
        base.reason = "not classified with an artifact_type, so it can never be a cross-model source"
        return base

    if not previous.model_agnostic_fingerprint:
        base.reason = "no model-agnostic fingerprint recorded on this computation"
        return base

    if not is_reusable(to_stored(previous)):
        base.reason = "expired or marked not reusable"
        return base

    if not await resolve_portability(session, scope, previous.artifact_type):
        base.reason = f"artifact_type '{previous.artifact_type}' is not portable per policy"
        return base

    base.decision = "REUSE"
    base.reason = (
        f"portable {previous.artifact_type}; only the model would change "
        f"({previous.model} -> {target_model})"
    )
    base.cost_if_recomputed_usd = 0.0
    return base
