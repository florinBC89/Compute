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
from app.schemas.metrics import ProjectMetrics
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
    )
