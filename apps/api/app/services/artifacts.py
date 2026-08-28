"""Reusable-artifact queries (V0.2), shared by the developer dashboard
(app.routes.metrics) and the human workspace (app.routes.workspace) -- one
query, two callers, so they can never quietly drift apart.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Computation


async def list_project_artifacts(
    session: AsyncSession, project_id: uuid.UUID, artifact_type: str | None = None
) -> list[Computation]:
    """The newest successful computation per logical key, classified with an
    artifact_type. ``DISTINCT ON`` is Postgres's idiomatic "latest row per
    group": ordering by ``(logical_key, seq DESC)`` and taking the first row
    per ``logical_key`` is exactly "the current version of each reusable
    artifact," the same definition ``find_previous`` uses for reuse lookups.
    """
    statement = (
        select(Computation)
        .distinct(Computation.logical_key)
        .where(
            Computation.project_id == project_id,
            Computation.status == "SUCCEEDED",
            Computation.artifact_type.is_not(None),
        )
    )
    if artifact_type is not None:
        statement = statement.where(Computation.artifact_type == artifact_type)
    statement = statement.order_by(Computation.logical_key, Computation.seq.desc())

    return list((await session.execute(statement)).scalars().all())


def artifact_list_item(row: Computation) -> dict:
    return {
        "logical_key": row.logical_key,
        "name": row.name,
        "artifact_type": row.artifact_type,
        "model": row.model,
        "reusable": bool(row.reusable),
        "cost_usd": float(row.cost_usd or 0),
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }
