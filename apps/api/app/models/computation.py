"""Computations (spec §6.4) -- the central table."""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_fk, uuid_pk

COMPUTATION_STATUSES = ("RUNNING", "SUCCEEDED", "FAILED")
CACHE_STATUSES = ("HIT", "MISS", "STALE", "FORCED")
#: V0.2 cross-model reuse (see artifact_policy.py). Deliberately not folded
#: into CACHE_STATUSES: a cross-model reuse is still, semantically, a HIT --
#: nothing was recomputed. reuse_kind records *why* separately, so every
#: consumer that doesn't know about it (hit-rate math, the dashboard's
#: CacheStatus union, the conformance scenarios) keeps seeing an ordinary,
#: correct HIT.
ARTIFACT_TYPES = (
    "source",
    "fact",
    "structured_data",
    "research_note",
    "analysis",
    "draft",
    "citation",
)
REUSE_KINDS = ("CROSS_MODEL",)


class Computation(Base):
    __tablename__ = "computations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED')",
            name="ck_computations_status",
        ),
        CheckConstraint(
            "cache_status IN ('HIT','MISS','STALE','FORCED')",
            name="ck_computations_cache_status",
        ),
        # The reuse lookup (§29) is the hot path: it filters on workspace,
        # project and fingerprint and takes the newest reusable row.
        Index(
            "idx_computations_fingerprint",
            "workspace_id",
            "project_id",
            "fingerprint",
        ),
        Index(
            "idx_computations_logical_key",
            "workspace_id",
            "project_id",
            "logical_key",
        ),
        Index("idx_computations_run", "run_id"),
        Index("idx_computations_created", "created_at"),
        # Partial indexes covering exactly the rows each lookup may return, so
        # the p95 < 100 ms target of §58 does not depend on table size.
        # Measured over 50k rows: 0.08 ms indexed vs 12.8 ms sequential.
        # Query predicates must be written as ``reusable = TRUE`` -- PostgreSQL
        # does not prove that ``reusable IS TRUE`` implies this predicate.
        Index(
            "idx_computations_reusable",
            "workspace_id",
            "project_id",
            "fingerprint",
            "seq",
            postgresql_where=text("status = 'SUCCEEDED' AND reusable = TRUE"),
        ),
        Index(
            "idx_computations_logical_reusable",
            "workspace_id",
            "project_id",
            "logical_key",
            "seq",
            postgresql_where=text("status = 'SUCCEEDED'"),
        ),
        # CHAR(64) in §6.4 implied a fixed-width hex digest but did not enforce
        # one, and in PostgreSQL ``bpchar`` compared against a text parameter is
        # cast to text, which makes the column's own index unusable. TEXT plus
        # an explicit format check gives the real guarantee without the trap.
        CheckConstraint(
            "fingerprint ~ '^[0-9a-f]{64}$'", name="ck_computations_fingerprint_hex"
        ),
        CheckConstraint(
            "logical_key ~ '^[0-9a-f]{64}$'", name="ck_computations_logical_key_hex"
        ),
        CheckConstraint(
            "output_hash IS NULL OR output_hash ~ '^[0-9a-f]{64}$'",
            name="ck_computations_output_hash_hex",
        ),
        CheckConstraint(
            "model_agnostic_fingerprint IS NULL OR "
            "model_agnostic_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_computations_model_agnostic_fingerprint_hex",
        ),
        CheckConstraint(
            "artifact_type IS NULL OR artifact_type IN "
            "('source','fact','structured_data','research_note','analysis',"
            "'draft','citation')",
            name="ck_computations_artifact_type",
        ),
        CheckConstraint(
            "reuse_kind IS NULL OR reuse_kind IN ('CROSS_MODEL')",
            name="ck_computations_reuse_kind",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    #: Monotonic insertion order. "The newest valid computation" (§17, §21) is
    #: resolved by this, not by created_at: created_at defaults to now(), which
    #: is *transaction* time, so any two rows written in one transaction carry
    #: an identical value and the ORDER BY becomes unstable. Measured: with tied
    #: timestamps PostgreSQL returned the older row on every attempt.
    seq: Mapped[int] = mapped_column(
        BigInteger, Identity(), nullable=False, unique=True
    )
    workspace_id: Mapped[uuid.UUID] = uuid_fk("workspaces.id")
    project_id: Mapped[uuid.UUID] = uuid_fk("projects.id")
    run_id: Mapped[uuid.UUID | None] = uuid_fk("runs.id", nullable=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    logical_key: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False)
    cache_status: Mapped[str] = mapped_column(Text, nullable=False)

    input_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Outputs are arbitrary JSON, not necessarily objects.
    output_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    output_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_schema_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_version: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: build_model_agnostic_fingerprint() -- same as `fingerprint` but with
    #: `model` excluded from the hash. Populated on every computation
    #: regardless of whether that call opted into cross-model reuse, so any
    #: past row can become a future cross-model source.
    model_agnostic_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Portable-artifact taxonomy (see ARTIFACT_TYPES). NULL means "not
    #: classified" -- ineligible as a cross-model source, not an error.
    artifact_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Set on HIT observation rows produced via cross-model reuse (see
    #: artifact_policy.py). NULL for an ordinary same-model HIT.
    reuse_kind: Mapped[str | None] = mapped_column(Text, nullable=True)

    input_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    output_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    cost_usd: Mapped[float] = mapped_column(
        Numeric(18, 8), nullable=False, default=0, server_default="0"
    )
    saved_usd: Mapped[float] = mapped_column(
        Numeric(18, 8), nullable=False, default=0, server_default="0"
    )
    latency_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ttl_seconds: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    reusable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    #: Set on HIT observation rows: the computation whose output was reused.
    #: A real column rather than a metadata key, so "tokens avoided" is a plain
    #: indexed join instead of a cast out of JSONB.
    reused_from: Mapped[uuid.UUID | None] = uuid_fk("computations.id", nullable=True)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )

    started_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
