"""Run endpoints (spec §34, §35).

``POST /runs`` and ``POST /runs/{id}/finish`` are additions: §6.3 defines the
``runs`` table and every other endpoint takes a ``run_id``, but the spec never
says how one is opened or closed.
"""

from __future__ import annotations

import datetime as _dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Computation, ComputationDependency, Run
from app.schemas.run import (
    RunCreateBody,
    RunCreateResponse,
    RunFinishBody,
    RunGraph,
    RunList,
    RunListItem,
    RunSummary,
)
from app.services.scope import Scope, resolve_scope

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=RunList)
async def list_runs(
    limit: int = 50,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> RunList:
    """Newest-first run listing (spec §52's Runs table implies this exists,
    though only ``GET /runs/{id}`` is specified)."""
    limit = max(1, min(limit, 200))
    runs = (
        (
            await session.execute(
                select(Run)
                .where(Run.project_id == scope.project_id)
                .order_by(Run.started_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    if not runs:
        return RunList(runs=[])

    run_ids = [run.id for run in runs]
    counts = (
        await session.execute(
            select(
                Computation.run_id,
                Computation.cache_status,
                func.count(Computation.id),
            )
            .where(Computation.run_id.in_(run_ids))
            .group_by(Computation.run_id, Computation.cache_status)
        )
    ).all()
    sums = (
        await session.execute(
            select(
                Computation.run_id,
                func.coalesce(func.sum(Computation.cost_usd), 0),
                func.coalesce(func.sum(Computation.saved_usd), 0),
                func.coalesce(func.sum(Computation.input_tokens), 0),
                func.coalesce(func.sum(Computation.output_tokens), 0),
            )
            .where(Computation.run_id.in_(run_ids))
            .group_by(Computation.run_id)
        )
    ).all()

    source = aliased(Computation)
    avoided = (
        await session.execute(
            select(
                Computation.run_id,
                func.coalesce(
                    func.sum(source.input_tokens + source.output_tokens), 0
                ),
                func.count(),
            )
            .select_from(Computation)
            .join(source, Computation.reused_from == source.id)
            .where(Computation.run_id.in_(run_ids), Computation.cache_status == "HIT")
            .group_by(Computation.run_id)
        )
    ).all()

    status_counts: dict[uuid.UUID, dict[str, int]] = {run_id: {} for run_id in run_ids}
    for run_id, cache_status, count in counts:
        status_counts[run_id][cache_status] = int(count)
    run_totals = {row[0]: row[1:] for row in sums}
    run_avoided = {row[0]: (row[1], row[2]) for row in avoided}

    items = []
    for run in runs:
        by_status = status_counts[run.id]
        cost, saved, in_tok, out_tok = run_totals.get(run.id, (0, 0, 0, 0))
        tokens_avoided, llm_calls_avoided = run_avoided.get(run.id, (0, 0))
        items.append(
            RunListItem(
                id=str(run.id),
                status=run.status,
                external_run_id=run.external_run_id,
                computations=sum(by_status.values()),
                hits=by_status.get("HIT", 0),
                misses=by_status.get("MISS", 0),
                stale=by_status.get("STALE", 0),
                forced=by_status.get("FORCED", 0),
                total_cost_usd=float(cost),
                saved_usd=float(saved),
                input_tokens=int(in_tok),
                output_tokens=int(out_tok),
                tokens_avoided=int(tokens_avoided),
                llm_calls_avoided=int(llm_calls_avoided),
                started_at=run.started_at.isoformat(),
                finished_at=run.finished_at.isoformat() if run.finished_at else None,
            )
        )
    return RunList(runs=items)


@router.post("", response_model=RunCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    body: RunCreateBody,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> RunCreateResponse:
    run = Run(
        id=uuid.uuid4(),
        workspace_id=scope.workspace_id,
        project_id=scope.project_id,
        external_run_id=body.external_run_id,
        status="RUNNING",
        meta=body.metadata,
    )
    session.add(run)
    await session.flush()
    return RunCreateResponse(id=str(run.id))


@router.post("/{run_id}/finish", response_model=RunSummary)
async def finish_run(
    run_id: uuid.UUID,
    body: RunFinishBody,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> RunSummary:
    run = await _load_run(session, scope, run_id)
    totals = await _totals(session, run_id)

    run.status = body.status
    run.finished_at = _dt.datetime.now(_dt.timezone.utc)
    run.total_input_tokens = totals["input_tokens"]
    run.total_output_tokens = totals["output_tokens"]
    run.estimated_cost_usd = totals["total_cost_usd"]
    run.estimated_saved_usd = totals["saved_usd"]

    return RunSummary(id=str(run.id), status=run.status, **totals)


@router.get("/{run_id}", response_model=RunSummary)
async def get_run(
    run_id: uuid.UUID,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> RunSummary:
    run = await _load_run(session, scope, run_id)
    return RunSummary(
        id=str(run.id), status=run.status, **(await _totals(session, run_id))
    )


@router.get("/{run_id}/graph", response_model=RunGraph)
async def get_run_graph(
    run_id: uuid.UUID,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> RunGraph:
    await _load_run(session, scope, run_id)

    rows = (
        await session.execute(
            select(Computation)
            .where(Computation.run_id == run_id)
            .order_by(Computation.created_at)
        )
    ).scalars().all()
    ids = {row.id for row in rows}

    edges = (
        await session.execute(
            select(ComputationDependency).where(
                ComputationDependency.computation_id.in_(ids or {uuid.uuid4()}),
                ComputationDependency.source_computation_id.is_not(None),
            )
        )
    ).scalars().all()

    # The real "previous execution" numbers for the Why? panel (HIT nodes
    # only) -- not estimated from this run's own (zeroed) cost/tokens.
    reused_from_ids = {row.reused_from for row in rows if row.reused_from}
    sources_by_id: dict[uuid.UUID, Computation] = {}
    if reused_from_ids:
        source_rows = (
            await session.execute(
                select(Computation).where(Computation.id.in_(reused_from_ids))
            )
        ).scalars().all()
        sources_by_id = {row.id: row for row in source_rows}

    def _node(row: Computation) -> dict:
        source = sources_by_id.get(row.reused_from) if row.reused_from else None
        return {
            "id": str(row.id),
            "name": row.name,
            "status": row.cache_status,
            "cost_usd": float(row.cost_usd or 0),
            "saved_usd": float(row.saved_usd or 0),
            "latency_ms": row.latency_ms,
            "input_tokens": int(row.input_tokens or 0),
            "output_tokens": int(row.output_tokens or 0),
            "previous_cost_usd": float(source.cost_usd or 0) if source else None,
            "previous_input_tokens": int(source.input_tokens or 0) if source else None,
            "previous_output_tokens": int(source.output_tokens or 0)
            if source
            else None,
            "previous_latency_ms": source.latency_ms if source else None,
        }

    return RunGraph(
        nodes=[_node(row) for row in rows],
        edges=[
            {
                "from": str(edge.source_computation_id),
                "to": str(edge.computation_id),
                "key": edge.dependency_key,
            }
            for edge in edges
            if edge.source_computation_id in ids
        ],
    )


async def _load_run(session: AsyncSession, scope: Scope, run_id: uuid.UUID) -> Run:
    run = await session.get(Run, run_id)
    if run is None or run.project_id != scope.project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="run not found"
        )
    return run


async def _totals(session: AsyncSession, run_id: uuid.UUID) -> dict:
    counts = dict(
        (
            await session.execute(
                select(Computation.cache_status, func.count(Computation.id))
                .where(Computation.run_id == run_id)
                .group_by(Computation.cache_status)
            )
        ).all()
    )
    sums = (
        await session.execute(
            select(
                func.coalesce(func.sum(Computation.cost_usd), 0),
                func.coalesce(func.sum(Computation.saved_usd), 0),
                func.coalesce(func.sum(Computation.input_tokens), 0),
                func.coalesce(func.sum(Computation.output_tokens), 0),
            ).where(Computation.run_id == run_id)
        )
    ).first()

    # Same join-on-reused_from pattern as the project metrics endpoint: what
    # each HIT would have cost in tokens/LLM-calls, counted once per reuse.
    source = aliased(Computation)
    tokens_avoided = (
        await session.execute(
            select(
                func.coalesce(func.sum(source.input_tokens + source.output_tokens), 0)
            )
            .select_from(Computation)
            .join(source, Computation.reused_from == source.id)
            .where(Computation.run_id == run_id, Computation.cache_status == "HIT")
        )
    ).scalar_one()
    llm_calls_avoided = (
        await session.execute(
            select(func.count())
            .select_from(Computation)
            .join(source, Computation.reused_from == source.id)
            .where(
                Computation.run_id == run_id,
                Computation.cache_status == "HIT",
                source.model.is_not(None),
            )
        )
    ).scalar_one()

    return {
        "computations": sum(int(value) for value in counts.values()),
        "hits": int(counts.get("HIT", 0)),
        "misses": int(counts.get("MISS", 0)),
        "stale": int(counts.get("STALE", 0)),
        "forced": int(counts.get("FORCED", 0)),
        "total_cost_usd": float(sums[0]),
        "saved_usd": float(sums[1]),
        "input_tokens": int(sums[2]),
        "output_tokens": int(sums[3]),
        "tokens_avoided": int(tokens_avoided or 0),
        "llm_calls_avoided": int(llm_calls_avoided or 0),
    }
