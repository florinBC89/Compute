"""Request/response models for the computation endpoints (spec §29-§32)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ArtifactType = Literal[
    "source", "fact", "structured_data", "research_note", "analysis", "draft", "citation"
]


class DependencyPayload(BaseModel):
    key: str
    version: str
    type: Literal[
        "EXTERNAL", "COMPUTATION", "FILE", "API", "DATABASE", "MANUAL"
    ] = "EXTERNAL"
    source_computation_id: str | None = None


class ExecutionPayload(BaseModel):
    model: str | None = None
    provider: str | None = None
    prompt_hash: str | None = None
    tool_schema_hash: str | None = None
    code_version: str | None = None


class LookupRequestBody(BaseModel):
    name: str
    logical_key: str = Field(min_length=64, max_length=64)
    fingerprint: str = Field(min_length=64, max_length=64)
    run_id: str | None = None
    ttl_seconds: int | None = None
    force: bool = False
    #: Sent so a recorded cache hit can carry its edges into the run graph.
    dependencies: list[DependencyPayload] = Field(default_factory=list)
    #: V0.2 cross-model reuse -- see computelayer.semantics.upgrade_for_cross_model.
    cross_model_reuse: bool = False
    artifact_type: ArtifactType | None = None
    model_agnostic_fingerprint: str = ""
    #: The model this call actually requested -- see LookupRequest.model in
    #: computelayer.semantics for why this needs to travel separately from
    #: fingerprint/model_agnostic_fingerprint.
    model: str | None = None


class LookupHitComputation(BaseModel):
    id: str
    source_computation_id: str
    output: Any = None
    output_hash: str | None = None
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: str | None = None


class LookupResponse(BaseModel):
    status: Literal["HIT", "MISS", "STALE", "FORCED"]
    computation: LookupHitComputation | None = None
    previous_computation_id: str | None = None
    reason: str = ""
    #: "CROSS_MODEL" when this HIT came from a portable artifact reused
    #: across a model switch; None for an ordinary HIT or any other status.
    reuse_kind: Literal["CROSS_MODEL"] | None = None


class StartRequestBody(BaseModel):
    name: str
    logical_key: str = Field(min_length=64, max_length=64)
    fingerprint: str = Field(min_length=64, max_length=64)
    run_id: str | None = None
    cache_status: Literal["MISS", "STALE", "FORCED"] = "MISS"
    input_json: Any = None
    dependencies: list[DependencyPayload] = Field(default_factory=list)
    execution: ExecutionPayload = Field(default_factory=ExecutionPayload)
    ttl_seconds: int | None = None
    reusable: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifact_type: ArtifactType | None = None
    model_agnostic_fingerprint: str | None = None


class StartResponse(BaseModel):
    computation_id: str


class CompleteRequestBody(BaseModel):
    output_json: Any = None
    output_hash: str = Field(min_length=64, max_length=64)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int | None = None
    model: str | None = None
    provider: str | None = None


class FailRequestBody(BaseModel):
    error_type: str
    error_message: str = ""


class StatusResponse(BaseModel):
    status: str


class ExplainChange(BaseModel):
    kind: str
    key: str | None = None
    old: str | None = None
    new: str | None = None


class ExplainResponse(BaseModel):
    computation_id: str
    name: str
    cache_status: str
    previous_computation_id: str | None = None
    changes: list[ExplainChange] = Field(default_factory=list)
