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
    "upgrade_for_cross_model",
    "DEFAULT_PORTABLE_ARTIFACT_TYPES",
]

#: Fallback portability defaults for V0.2 cross-model reuse, used when no
#: policy row overrides them. ``LocalBackend`` always uses this directly (it
#: has no real policy store); the API only falls back to it when neither a
#: project- nor workspace-level ``artifact_type_policies`` row exists (see
#: ``apps/api/app/services/artifact_policy.py``).
#:
#: All seven artifact types default to portable. This isn't a claim that
#: model switches never affect a "draft" or "analysis" -- it's that (a) a
#: workspace/project can dial any type down to non-portable via the policy
#: table, (b) reuse additionally requires the model-agnostic fingerprint to
#: match, i.e. nothing about the inputs, dependencies, prompt or code
#: actually changed, and (c) it's opt-in per call via
#: ``cross_model_reuse=True``, so a caller decides per artifact whether to
#: even attempt it -- these three gates matter more than the taxonomy label.
DEFAULT_PORTABLE_ARTIFACT_TYPES: frozenset[str] = frozenset(
    {
        "source",
        "fact",
        "structured_data",
        "research_note",
        "analysis",
        "draft",
        "citation",
    }
)


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

    # V0.2 cross-model reuse. Optional and default-None so the eight pinned
    # conformance scenarios, which never set these, are unaffected.
    model: str | None = None
    artifact_type: str | None = None
    model_agnostic_fingerprint: str | None = None


@dataclass
class LookupRequest:
    """Body of ``POST /v1/computations/lookup`` (§29)."""

    name: str
    logical_key: str
    fingerprint: str
    run_id: str | None = None
    ttl_seconds: int | None = None
    force: bool = False

    # V0.2 cross-model reuse -- additive, defaults preserve existing callers.
    cross_model_reuse: bool = False
    artifact_type: str | None = None
    model_agnostic_fingerprint: str = ""
    #: The model this call actually asked for. Only `fingerprint` (which
    #: bakes model in) and `model_agnostic_fingerprint` (which never does)
    #: travelled to the server before this -- neither lets a HIT observation
    #: row record what was *requested* when it differs from the reused
    #: source, which is exactly what a cross-model HIT needs to show in
    #: /explain ("model changed: gpt-4o -> claude-3-5-sonnet").
    model: str | None = None


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


def upgrade_for_cross_model(
    outcome: LookupOutcome,
    request: LookupRequest,
    previous: StoredComputation | None,
    *,
    is_portable: bool,
    now: _dt.datetime | None = None,
    max_age_seconds: int | None = None,
) -> LookupOutcome:
    """V0.2: upgrade a STALE outcome to HIT when only the model changed.

    Deliberately separate from :func:`classify` rather than folded into it:
    ``classify``'s default output is pinned by eight conformance scenarios run
    against both the real API and :mod:`computelayer.testing`'s in-memory
    backend, and a model switch changing the default outcome would silently
    break that contract. This function only ever *upgrades* STALE to HIT, and
    only when the caller explicitly opts in via ``request.cross_model_reuse``
    -- callers who never pass it see byte-for-byte the same behavior as
    before this function existed.

    ``is_portable`` is resolved by the caller (the real API via a DB-backed
    policy table; :class:`~computelayer.testing.LocalBackend` via a hardcoded
    default map) so this function -- like the rest of this module -- stays
    free of any I/O.

    A cross-model reuse is recorded as an ordinary HIT, not a new
    ``CacheStatus`` value: no compute happened, which is exactly what HIT
    means. The caller is expected to additionally record *why* (e.g. a
    ``reuse_kind="CROSS_MODEL"`` column) outside of this dataclass.
    """
    if outcome.status != CacheStatus.STALE or not request.cross_model_reuse:
        return outcome
    if previous is None or not is_portable:
        return outcome
    if not previous.model_agnostic_fingerprint:
        return outcome
    if previous.model_agnostic_fingerprint != request.model_agnostic_fingerprint:
        return outcome
    if not is_reusable(previous, now, max_age_seconds):
        return outcome
    return LookupOutcome(
        status=CacheStatus.HIT,
        computation=previous,
        reason=f"cross-model reuse: portable {previous.artifact_type} artifact, "
        "only the model changed",
    )
