"""Model-switch preview (V0.2, spec section 4), shared by the developer
dashboard (app.routes.cross_model) and the human workspace
(app.routes.workspace) -- one evaluation, two callers, so they can never
quietly disagree about what a model switch would reuse.

Pure read: no lookup/start/complete calls, no stampede lock, no new
computation rows. For every distinct logical key a run produced, the
*current* best candidate for that key -- project-wide, not just that run,
matching how a real lookup resolves it -- is evaluated against the same
portability policy the real cross-model lookup path uses.
"""

from __future__ import annotations

import uuid

from computelayer.semantics import is_reusable
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Computation
from app.schemas.cross_model import (
    PreviewItem,
    PreviewModelSwitchResponse,
)
from app.services.artifact_policy import resolve_portability
from app.services.lookup import find_previous, to_stored
from app.services.scope import Scope

__all__ = ["build_preview"]


async def build_preview(
    session: AsyncSession, scope: Scope, run_id: uuid.UUID, target_model: str
) -> PreviewModelSwitchResponse:
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
        item = await _evaluate(session, scope, row.name, row.logical_key, previous, target_model)
        items.append(item)
        if item.decision == "RECOMPUTE":
            estimated_incremental_cost += item.cost_if_recomputed_usd

    reusable_count = sum(1 for item in items if item.decision == "REUSE")
    return PreviewModelSwitchResponse(
        target_model=target_model,
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
