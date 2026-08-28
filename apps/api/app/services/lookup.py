"""Reuse lookup against PostgreSQL (spec §17, §29).

The *decision* about HIT / MISS / STALE lives in
:mod:`computelayer.semantics`, which the in-memory reference backend
(``computelayer.testing.LocalBackend``) also uses.  This module's only job is
to fetch the two candidate rows the decision needs and to record the outcome.
Keeping the rules in one shared module is what stops the two backends from
quietly disagreeing -- and a disagreement here means incorrect reuse, the one
failure mode §61 says is unacceptable.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from computelayer.semantics import (
    LookupRequest,
    LookupOutcome,
    StoredComputation,
    classify,
    upgrade_for_cross_model,
)
from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Computation, ComputationDependency, ComputationEvent
from app.services.artifact_policy import resolve_portability
from app.services.scope import Scope

__all__ = [
    "find_exact",
    "find_previous",
    "resolve_lookup",
    "record_hit_observation",
    "to_stored",
]


def to_stored(row: Computation) -> StoredComputation:
    return StoredComputation(
        id=str(row.id),
        name=row.name,
        logical_key=row.logical_key,
        fingerprint=row.fingerprint,
        status=row.status,
        output_json=row.output_json,
        output_hash=row.output_hash,
        cost_usd=float(row.cost_usd or 0),
        input_tokens=int(row.input_tokens or 0),
        output_tokens=int(row.output_tokens or 0),
        latency_ms=row.latency_ms,
        reusable=bool(row.reusable),
        expires_at=row.expires_at,
        created_at=row.created_at,
        model=row.model,
        artifact_type=row.artifact_type,
        model_agnostic_fingerprint=row.model_agnostic_fingerprint,
    )


async def find_exact(
    session: AsyncSession, scope: Scope, fingerprint: str
) -> Computation | None:
    """Newest successful, reusable row with this exact fingerprint.

    Ordering is by ``seq``, not ``created_at``: ``created_at`` defaults to
    ``now()``, which is transaction time, so rows written in one transaction tie
    and the sort becomes unstable -- measured returning the *older* row every
    time.  ``seq`` is monotonic, so "newest" is exact.

    ``reusable == true()`` rather than ``reusable.is_(True)`` is deliberate and
    load-bearing: ``idx_computations_reusable`` is a partial index predicated on
    ``reusable = TRUE``, and PostgreSQL will not prove that ``reusable IS TRUE``
    implies that predicate.  With ``IS TRUE`` the planner falls back to a
    sequential scan -- measured at 12.8 ms over 50k rows and growing linearly,
    against the 100 ms p95 budget of §58.  With ``= TRUE`` the same lookup is an
    index scan at 0.08 ms.
    """
    statement = (
        select(Computation)
        .where(
            Computation.workspace_id == scope.workspace_id,
            Computation.project_id == scope.project_id,
            Computation.fingerprint == fingerprint,
            Computation.status == "SUCCEEDED",
            Computation.reusable == true(),
        )
        .order_by(Computation.seq.desc())
        .limit(1)
    )
    return (await session.execute(statement)).scalars().first()


async def find_previous(
    session: AsyncSession, scope: Scope, logical_key: str
) -> Computation | None:
    """Newest successful row for this logical computation, reusable or not.

    A previous *failure* does not count: a computation that produced no result
    is nothing for the new one to be stale against, so that case resolves to
    MISS.

    ``cache_status != 'HIT'`` excludes observation rows (see
    ``record_hit_observation``): those record that a reuse *happened*, but
    carry no output of their own (``output_json`` is always NULL) and no
    ``artifact_type``/``model_agnostic_fingerprint`` -- real bug, found via
    a real second-then-third cross-model switch: once one HIT observation
    existed for a logical key, it -- being the newest row -- shadowed the
    real classified computation underneath it, so every *subsequent* lookup
    or model-switch-preview for that key saw "not classified" and refused
    to reuse or preview a switch, even though a portable source genuinely
    existed one row down. Excluding HIT rows here is what keeps "reusable
    or not" (a real row that opted out of being a future source) from
    accidentally including "not a source at all" (a pure audit record).
    """
    statement = (
        select(Computation)
        .where(
            Computation.workspace_id == scope.workspace_id,
            Computation.project_id == scope.project_id,
            Computation.logical_key == logical_key,
            Computation.status == "SUCCEEDED",
            Computation.cache_status != "HIT",
        )
        .order_by(Computation.seq.desc())
        .limit(1)
    )
    return (await session.execute(statement)).scalars().first()


async def resolve_lookup(
    session: AsyncSession,
    scope: Scope,
    request: LookupRequest,
    now: _dt.datetime | None = None,
) -> tuple[LookupOutcome, Computation | None, str | None]:
    """Return the decision, the ORM row it was based on, and the reuse kind.

    ``reuse_kind`` is ``None`` for an ordinary same-fingerprint HIT and
    ``"CROSS_MODEL"`` when the HIT only exists because
    :func:`~computelayer.semantics.upgrade_for_cross_model` upgraded a STALE
    (§V0.2) -- in which case ``source`` is ``previous_row``, not
    ``exact_row``, since there was no exact fingerprint match to begin with.
    """
    exact_row = await find_exact(session, scope, request.fingerprint)
    previous_row = await find_previous(session, scope, request.logical_key)
    previous_stored = to_stored(previous_row) if previous_row is not None else None

    outcome = classify(
        request,
        to_stored(exact_row) if exact_row is not None else None,
        previous_stored,
        now,
    )

    is_portable = await resolve_portability(
        session, scope, previous_stored.artifact_type if previous_stored else None
    )
    outcome = upgrade_for_cross_model(
        outcome,
        request,
        previous_stored,
        is_portable=is_portable,
        now=now,
        max_age_seconds=request.ttl_seconds,
    )

    if outcome.status != "HIT" or outcome.computation is None:
        return outcome, None, None
    if exact_row is not None and outcome.computation.id == str(exact_row.id):
        return outcome, exact_row, None
    return outcome, previous_row, "CROSS_MODEL"


async def record_hit_observation(
    session: AsyncSession,
    scope: Scope,
    request: LookupRequest,
    source: Computation,
    dependencies: list[dict[str, Any]] | None,
    reuse_kind: str | None = None,
) -> Computation:
    """Write a node representing this run's reuse of ``source``.

    Recording the hit is what lets ``GET /v1/runs/{id}`` report a reuse rate and
    ``GET /v1/runs/{id}/graph`` draw a complete graph.  The observation row is
    marked ``reusable = FALSE`` and stores no output of its own, so it is never
    itself a reuse source -- lookups only ever resolve to real executions.
    """
    observation = Computation(
        id=uuid.uuid4(),
        workspace_id=scope.workspace_id,
        project_id=scope.project_id,
        run_id=uuid.UUID(request.run_id) if request.run_id else None,
        name=request.name,
        logical_key=request.logical_key,
        fingerprint=request.fingerprint,
        status="SUCCEEDED",
        cache_status="HIT",
        reuse_kind=reuse_kind,
        input_json=None,
        output_json=None,
        output_hash=source.output_hash,
        # The requested model when the caller sent one -- for an ordinary
        # HIT this is provably equal to source.model anyway (the fingerprint
        # match already guarantees it), but for a CROSS_MODEL HIT it's what
        # actually differs and what /explain needs to show.
        model=request.model or source.model,
        provider=source.provider,
        prompt_hash=source.prompt_hash,
        tool_schema_hash=source.tool_schema_hash,
        code_version=source.code_version,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0,
        saved_usd=source.cost_usd or 0,
        latency_ms=0,
        reusable=False,
        reused_from=source.id,
        meta={},
    )
    session.add(observation)
    await session.flush()

    for dependency in dependencies or []:
        session.add(
            ComputationDependency(
                id=uuid.uuid4(),
                computation_id=observation.id,
                dependency_key=dependency["key"],
                dependency_version=dependency["version"],
                dependency_type=dependency.get("type", "EXTERNAL"),
                source_computation_id=(
                    uuid.UUID(dependency["source_computation_id"])
                    if dependency.get("source_computation_id")
                    else None
                ),
            )
        )

    session.add(
        ComputationEvent(
            computation_id=observation.id,
            event_type="CACHE_HIT",
            payload={
                "source_computation_id": str(source.id),
                "reuse_kind": reuse_kind,
            },
        )
    )
    return observation
