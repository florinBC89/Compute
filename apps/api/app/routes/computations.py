"""Computation endpoints (spec §29-§32, §53)."""

from __future__ import annotations

import datetime as _dt
import uuid

from computelayer.semantics import LookupRequest
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Computation, ComputationDependency, ComputationEvent
from app.schemas.computation import (
    CompleteRequestBody,
    ExplainResponse,
    FailRequestBody,
    LookupRequestBody,
    LookupResponse,
    StartRequestBody,
    StartResponse,
    StatusResponse,
)
from app.services import storage
from app.services.lookup import record_hit_observation, resolve_lookup
from app.services.scope import Scope, resolve_scope

router = APIRouter(prefix="/computations", tags=["computations"])


@router.post("/lookup", response_model=LookupResponse)
async def lookup(
    body: LookupRequestBody,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> LookupResponse:
    """Decide whether a computation should execute.

    This is the hot path -- it runs before every agent step, so it stays to two
    indexed single-row queries plus, on a hit, one insert.
    """
    request = LookupRequest(
        name=body.name,
        logical_key=body.logical_key,
        fingerprint=body.fingerprint,
        run_id=body.run_id,
        ttl_seconds=body.ttl_seconds,
        force=body.force,
        cross_model_reuse=body.cross_model_reuse,
        artifact_type=body.artifact_type,
        model_agnostic_fingerprint=body.model_agnostic_fingerprint,
        model=body.model,
    )
    outcome, source, reuse_kind = await resolve_lookup(session, scope, request)

    if outcome.status != "HIT" or source is None:
        return LookupResponse(
            status=outcome.status,
            previous_computation_id=outcome.previous_computation_id,
            reason=outcome.reason,
        )

    observation = await record_hit_observation(
        session,
        scope,
        request,
        source,
        [dependency.model_dump() for dependency in body.dependencies],
        reuse_kind,
    )

    return LookupResponse(
        status="HIT",
        computation={
            "id": str(observation.id),
            "source_computation_id": str(source.id),
            "output": storage.load_output(source.output_json),
            "output_hash": source.output_hash,
            "cost_usd": float(source.cost_usd or 0),
            "input_tokens": int(source.input_tokens or 0),
            "output_tokens": int(source.output_tokens or 0),
            "created_at": source.created_at.isoformat() if source.created_at else None,
        },
        reason=outcome.reason,
        reuse_kind=reuse_kind,
    )


@router.post("/start", response_model=StartResponse, status_code=status.HTTP_201_CREATED)
async def start(
    body: StartRequestBody,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> StartResponse:
    """Record a computation that is about to execute (§30)."""
    now = _dt.datetime.now(_dt.timezone.utc)
    expires_at = (
        now + _dt.timedelta(seconds=body.ttl_seconds) if body.ttl_seconds else None
    )

    computation = Computation(
        id=uuid.uuid4(),
        workspace_id=scope.workspace_id,
        project_id=scope.project_id,
        run_id=uuid.UUID(body.run_id) if body.run_id else None,
        name=body.name,
        logical_key=body.logical_key,
        fingerprint=body.fingerprint,
        status="RUNNING",
        cache_status=body.cache_status,
        input_json=body.input_json,
        model=body.execution.model,
        provider=body.execution.provider,
        prompt_hash=body.execution.prompt_hash,
        tool_schema_hash=body.execution.tool_schema_hash,
        code_version=body.execution.code_version,
        ttl_seconds=body.ttl_seconds,
        reusable=body.reusable,
        meta=body.metadata,
        expires_at=expires_at,
        artifact_type=body.artifact_type,
        model_agnostic_fingerprint=body.model_agnostic_fingerprint,
    )
    session.add(computation)
    await session.flush()

    seen: set[str] = set()
    for dependency in body.dependencies:
        if dependency.key in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"duplicate dependency key {dependency.key!r}",
            )
        seen.add(dependency.key)
        session.add(
            ComputationDependency(
                id=uuid.uuid4(),
                computation_id=computation.id,
                dependency_key=dependency.key,
                dependency_version=dependency.version,
                dependency_type=dependency.type,
                source_computation_id=(
                    uuid.UUID(dependency.source_computation_id)
                    if dependency.source_computation_id
                    else None
                ),
            )
        )

    session.add(
        ComputationEvent(
            computation_id=computation.id,
            event_type="EXECUTION_STARTED",
            payload={"name": body.name, "cache_status": body.cache_status},
        )
    )
    return StartResponse(computation_id=str(computation.id))


@router.post("/{computation_id}/complete", response_model=StatusResponse)
async def complete(
    computation_id: uuid.UUID,
    body: CompleteRequestBody,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    """Record a successful execution (§31)."""
    computation = await _load(session, scope, computation_id)

    computation.status = "SUCCEEDED"
    computation.output_json = storage.store_output(body.output_json, body.output_hash)
    computation.output_hash = body.output_hash
    computation.input_tokens = body.input_tokens
    computation.output_tokens = body.output_tokens
    computation.cost_usd = body.cost_usd
    computation.latency_ms = body.latency_ms
    computation.completed_at = _dt.datetime.now(_dt.timezone.utc)
    if body.model:
        computation.model = body.model
    if body.provider:
        computation.provider = body.provider

    session.add_all(
        [
            ComputationEvent(
                computation_id=computation.id,
                event_type="OUTPUT_HASHED",
                payload={"output_hash": body.output_hash},
            ),
            ComputationEvent(
                computation_id=computation.id, event_type="RESULT_STORED", payload={}
            ),
        ]
    )
    return StatusResponse(status="SUCCEEDED")


@router.post("/{computation_id}/fail", response_model=StatusResponse)
async def fail(
    computation_id: uuid.UUID,
    body: FailRequestBody,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    """Record a failure (§32). Failed computations are never reused (§3)."""
    computation = await _load(session, scope, computation_id)

    computation.status = "FAILED"
    computation.reusable = False
    computation.completed_at = _dt.datetime.now(_dt.timezone.utc)
    computation.meta = {
        **(computation.meta or {}),
        "error_type": body.error_type,
        "error_message": body.error_message[:2000],
    }

    session.add(
        ComputationEvent(
            computation_id=computation.id,
            event_type="EXECUTION_FAILED",
            payload={"error_type": body.error_type, "error_message": body.error_message},
        )
    )
    return StatusResponse(status="FAILED")


@router.get("/{computation_id}/explain", response_model=ExplainResponse)
async def explain(
    computation_id: uuid.UUID,
    scope: Scope = Depends(resolve_scope),
    session: AsyncSession = Depends(get_session),
) -> ExplainResponse:
    """Why did this computation run? (§53)"""
    computation = await _load(session, scope, computation_id)

    previous = (
        await session.execute(
            select(Computation)
            .where(
                Computation.workspace_id == scope.workspace_id,
                Computation.project_id == scope.project_id,
                Computation.logical_key == computation.logical_key,
                Computation.id != computation.id,
                Computation.seq < computation.seq,
                Computation.status == "SUCCEEDED",
            )
            .order_by(Computation.seq.desc())
            .limit(1)
        )
    ).scalars().first()

    changes: list[dict[str, str | None]] = []
    if previous is not None:
        old = await _dependency_map(session, previous.id)
        new = await _dependency_map(session, computation.id)
        for key, version in new.items():
            if key not in old:
                changes.append({"kind": "dependency_added", "key": key, "new": version})
            elif old[key] != version:
                changes.append(
                    {
                        "kind": "dependency_changed",
                        "key": key,
                        "old": old[key],
                        "new": version,
                    }
                )
        for key in old.keys() - new.keys():
            changes.append({"kind": "dependency_removed", "key": key, "old": old[key]})
        for field in ("model", "prompt_hash", "tool_schema_hash", "code_version"):
            if getattr(previous, field) != getattr(computation, field):
                changes.append(
                    {
                        "kind": f"{field}_changed",
                        "old": getattr(previous, field),
                        "new": getattr(computation, field),
                    }
                )

    return ExplainResponse(
        computation_id=str(computation.id),
        name=computation.name,
        cache_status=computation.cache_status,
        previous_computation_id=str(previous.id) if previous else None,
        changes=changes,
    )


async def _load(
    session: AsyncSession, scope: Scope, computation_id: uuid.UUID
) -> Computation:
    computation = await session.get(Computation, computation_id)
    if computation is None or computation.project_id != scope.project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="computation not found"
        )
    return computation


async def _dependency_map(session: AsyncSession, computation_id: uuid.UUID) -> dict:
    rows = (
        await session.execute(
            select(ComputationDependency).where(
                ComputationDependency.computation_id == computation_id
            )
        )
    ).scalars().all()
    return {row.dependency_key: row.dependency_version for row in rows}
