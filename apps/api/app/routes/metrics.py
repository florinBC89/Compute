"""Project metrics (spec §36)."""

from __future__ import annotations

import datetime as _dt
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Computation, Run
from app.schemas.metrics import (
    ArtifactListResponse,
    ProjectMetrics,
    UsageBreakdownItem,
    UsageResponse,
)
from app.services.scope import Scope, resolve_scope

router = APIRouter(prefix="/projects", tags=["metrics"])

_PERIOD = re.compile(r"^(\d+)([dhw])$")
_UNITS = {"h": "hours", "d": "days", "w": "weeks"}


def _period_start(period: str) -> _dt.datetime:
    match = _PERIOD.match(period)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period must look like 24h, 30d or 2w",
        )
    amount, unit = int(match.group(1)), match.group(2)
    return _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(**{_UNITS[unit]: amount})


@router.get("/{project_slug}/metrics", response_model=ProjectMetrics)
async def project_metrics(
    project_slug: str,
    period: str = "30d",
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> ProjectMetrics:
    since = _period_start(period)

    counts = dict(
        (
            await session.execute(
                select(Computation.cache_status, func.count(Computation.id))
                .where(
                    Computation.project_id == scope.project_id,
                    Computation.created_at >= since,
                )
                .group_by(Computation.cache_status)
            )
        ).all()
    )
    total = sum(int(value) for value in counts.values())
    hits = int(counts.get("HIT", 0))

    sums = (
        await session.execute(
            select(
                func.coalesce(func.sum(Computation.cost_usd), 0),
                func.coalesce(func.sum(Computation.saved_usd), 0),
                func.coalesce(func.sum(Computation.input_tokens), 0),
                func.coalesce(func.sum(Computation.output_tokens), 0),
            ).where(
                Computation.project_id == scope.project_id,
                Computation.created_at >= since,
            )
        )
    ).first()

    # Tokens avoided: what each reuse would have cost, counted once per HIT.
    #
    # Joining rather than using IN(subquery) is deliberate. A source reused
    # twenty times avoided its tokens twenty times, and IN() would dedupe the
    # ids and report it once -- understating the headline number this endpoint
    # exists to produce. The join also needs an alias: both sides are
    # `computations`, and without one SQLAlchemy correlates the subquery to the
    # outer query and silently returns the wrong rows.
    source = aliased(Computation)
    avoided = (
        await session.execute(
            select(
                func.coalesce(
                    func.sum(source.input_tokens + source.output_tokens), 0
                )
            )
            .select_from(Computation)
            .join(source, Computation.reused_from == source.id)
            .where(
                Computation.project_id == scope.project_id,
                Computation.created_at >= since,
                Computation.cache_status == "HIT",
            )
        )
    ).scalar_one()

    llm_calls_avoided = (
        await session.execute(
            select(func.count())
            .select_from(Computation)
            .join(source, Computation.reused_from == source.id)
            .where(
                Computation.project_id == scope.project_id,
                Computation.created_at >= since,
                Computation.cache_status == "HIT",
                source.model.is_not(None),
            )
        )
    ).scalar_one()

    # V0.2: same join, narrowed to HITs recorded with reuse_kind="CROSS_MODEL"
    # -- a strict subset of the totals above, not additional to them.
    cross_model = (
        await session.execute(
            select(
                func.coalesce(func.sum(source.cost_usd), 0),
                func.coalesce(
                    func.sum(source.input_tokens + source.output_tokens), 0
                ),
            )
            .select_from(Computation)
            .join(source, Computation.reused_from == source.id)
            .where(
                Computation.project_id == scope.project_id,
                Computation.created_at >= since,
                Computation.cache_status == "HIT",
                Computation.reuse_kind == "CROSS_MODEL",
            )
        )
    ).first()

    runs = (
        await session.execute(
            select(func.count(Run.id)).where(
                Run.project_id == scope.project_id, Run.started_at >= since
            )
        )
    ).scalar_one()

    return ProjectMetrics(
        period=period,
        runs=int(runs),
        computations=total,
        hit_rate=(hits / total) if total else 0.0,
        cost_usd=float(sums[0]),
        saved_usd=float(sums[1]),
        tokens_consumed=int(sums[2]) + int(sums[3]),
        tokens_avoided=int(avoided or 0),
        llm_calls_avoided=int(llm_calls_avoided or 0),
        cross_model_saved_usd=float(cross_model[0]) if cross_model else 0.0,
        cross_model_tokens_avoided=int(cross_model[1]) if cross_model else 0,
    )


@router.get("/{project_slug}/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(
    project_slug: str,
    artifact_type: str | None = None,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> ArtifactListResponse:
    """The newest successful computation per logical key, classified with an
    artifact_type (V0.2). Backs the dashboard's Projects page.

    ``DISTINCT ON`` is Postgres's idiomatic "latest row per group": ordering
    by ``(logical_key, seq DESC)`` and taking the first row per
    ``logical_key`` is exactly "the current version of each reusable
    artifact," the same definition ``find_previous`` uses for reuse lookups.
    """
    statement = (
        select(Computation)
        .distinct(Computation.logical_key)
        .where(
            Computation.project_id == scope.project_id,
            Computation.status == "SUCCEEDED",
            Computation.artifact_type.is_not(None),
        )
    )
    if artifact_type is not None:
        statement = statement.where(Computation.artifact_type == artifact_type)
    statement = statement.order_by(Computation.logical_key, Computation.seq.desc())

    rows = (await session.execute(statement)).scalars().all()
    return ArtifactListResponse(
        artifacts=[
            {
                "logical_key": row.logical_key,
                "name": row.name,
                "artifact_type": row.artifact_type,
                "model": row.model,
                "reusable": bool(row.reusable),
                "cost_usd": float(row.cost_usd or 0),
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
            for row in rows
        ]
    )


@router.get("/{project_slug}/usage", response_model=UsageResponse)
async def usage(
    project_slug: str,
    period: str = "30d",
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> UsageResponse:
    """Cost and tokens broken down by model and task name (V0.2).

    Real executions only (``cache_status`` other than ``HIT``): a HIT
    observation row's own cost/tokens are zeroed by design (its cost is
    recorded as *avoided*, on the source row), so including them here would
    silently understate every model's real usage.
    """
    since = _period_start(period)
    rows = (
        await session.execute(
            select(
                Computation.model,
                Computation.name,
                func.count(),
                func.coalesce(func.sum(Computation.cost_usd), 0),
                func.coalesce(func.sum(Computation.input_tokens), 0),
                func.coalesce(func.sum(Computation.output_tokens), 0),
            )
            .where(
                Computation.project_id == scope.project_id,
                Computation.created_at >= since,
                Computation.cache_status != "HIT",
            )
            .group_by(Computation.model, Computation.name)
            .order_by(func.sum(Computation.cost_usd).desc())
        )
    ).all()

    return UsageResponse(
        period=period,
        items=[
            UsageBreakdownItem(
                model=model,
                name=name,
                computations=int(count),
                cost_usd=float(cost),
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
            )
            for model, name, count, cost, input_tokens, output_tokens in rows
        ],
    )
