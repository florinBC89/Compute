"""Reuse semantics (spec §17, §20).

These functions are the single source of truth for *when a stored computation
may be reused* and *how a lookup is classified*.  They are pure, dependency
free, and imported by both the in-memory backend
(:mod:`computelayer.testing`) and the PostgreSQL-backed API
(``apps/api/app/services/lookup.py``) so the two can never drift apart.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from computelayer.result import CacheStatus, ComputationStatus

__all__ = [
    "StoredComputation",
    "LookupRequest",
    "LookupOutcome",
    "utcnow",
    "is_reusable",
    "classify",
]


def utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _as_aware(value: _dt.datetime | None) -> _dt.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=_dt.timezone.utc)
    return value


@dataclass
class StoredComputation:
    """The subset of a ``computations`` row that reuse decisions depend on."""

    id: str
    name: str
    logical_key: str
    fingerprint: str
    status: str
    output_json: Any = None
    output_hash: str | None = None
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int | None = None
    reusable: bool = True
    expires_at: _dt.datetime | None = None
    created_at: _dt.datetime = field(default_factory=utcnow)


@dataclass
class LookupRequest:
    """Body of ``POST /v1/computations/lookup`` (§29)."""

    name: str
    logical_key: str
    fingerprint: str
    run_id: str | None = None
    ttl_seconds: int | None = None
    force: bool = False


@dataclass
class LookupOutcome:
    status: str
    computation: StoredComputation | None = None
    previous_computation_id: str | None = None
    reason: str = ""


def is_reusable(
    row: StoredComputation,
    now: _dt.datetime | None = None,
    max_age_seconds: int | None = None,
) -> bool:
    """A computation is reusable only if all of §20 holds.

    ``max_age_seconds`` lets a caller apply a *tighter* TTL at lookup time than
    the one recorded when the row was written, so lowering a ``ttl=`` argument
    takes effect immediately instead of on the next write.
    """
    now = now or utcnow()

    if row.status != ComputationStatus.SUCCEEDED:
        return False  # failed computations must never be reused (§3)
    if not row.reusable:
        return False

    expires_at = _as_aware(row.expires_at)
    if expires_at is not None and expires_at <= now:
        return False

    if max_age_seconds is not None:
        created_at = _as_aware(row.created_at) or now
        if (now - created_at).total_seconds() > max_age_seconds:
            return False

    return True


def classify(
    request: LookupRequest,
    exact: StoredComputation | None,
    previous: StoredComputation | None,
    now: _dt.datetime | None = None,
) -> LookupOutcome:
    """Resolve a lookup to HIT / MISS / STALE / FORCED (§17).

    ``exact``     -- newest successful row with this exact fingerprint.
    ``previous``  -- newest successful row with this logical key.
    """
    now = now or utcnow()

    # Step 3 -- force short-circuits before any reusable lookup occurs.
    if request.force:
        return LookupOutcome(
            status=CacheStatus.FORCED,
            previous_computation_id=previous.id if previous else None,
            reason="force=True was requested",
        )

    # Step 1 -- exact fingerprint match that is still valid.
    if exact is not None and is_reusable(exact, now, request.ttl_seconds):
        return LookupOutcome(
            status=CacheStatus.HIT,
            computation=exact,
            reason="exact fingerprint match",
        )

    # Step 2 -- an older version of the same logical computation exists.
    if previous is not None:
        if exact is not None:
            reason = "matching fingerprint exists but is expired or not reusable"
        else:
            reason = "inputs, dependencies or execution parameters changed"
        return LookupOutcome(
            status=CacheStatus.STALE,
            previous_computation_id=previous.id,
            reason=reason,
        )

    return LookupOutcome(
        status=CacheStatus.MISS,
        reason="no previous computation with this logical key",
    )
