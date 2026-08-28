"""Run summary/graph queries (spec §34-35), shared by the developer
dashboard (app.routes.runs) and the human workspace (app.routes.workspace)
-- one query, two callers, so they can never quietly drift apart.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Computation, ComputationDependency

__all__ = ["run_totals", "run_graph_data"]


async def run_totals(session: AsyncSession, run_id: uuid.UUID) -> dict:
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


async def run_graph_data(session: AsyncSession, run_id: uuid.UUID) -> dict:
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
            "reuse_kind": row.reuse_kind,
        }

    return {
        "nodes": [_node(row) for row in rows],
        "edges": [
            {
                "from": str(edge.source_computation_id),
                "to": str(edge.computation_id),
                "key": edge.dependency_key,
            }
            for edge in edges
            if edge.source_computation_id in ids
        ],
    }
