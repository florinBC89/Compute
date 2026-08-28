"""Project metrics (spec §36)."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.computation import ArtifactType


class ProjectMetrics(BaseModel):
    period: str
    runs: int
    computations: int
    hit_rate: float
    cost_usd: float
    saved_usd: float
    tokens_consumed: int
    tokens_avoided: int
    llm_calls_avoided: int = 0
    #: V0.2: the subset of saved_usd/tokens_avoided that came specifically
    #: from reusing a portable artifact across a model switch, rather than an
    #: ordinary same-model HIT. A strict subset of saved_usd/tokens_avoided,
    #: not additional to them.
    cross_model_saved_usd: float = 0.0
    cross_model_tokens_avoided: int = 0


class ArtifactListItem(BaseModel):
    """The newest successful computation for one logical key (V0.2)."""

    logical_key: str
    name: str
    artifact_type: ArtifactType | None
    model: str | None
    reusable: bool
    cost_usd: float
    created_at: str


class ArtifactListResponse(BaseModel):
    artifacts: list[ArtifactListItem]


class UsageBreakdownItem(BaseModel):
    model: str | None
    name: str
    computations: int
    cost_usd: float
    input_tokens: int
    output_tokens: int


class UsageResponse(BaseModel):
    period: str
    items: list[UsageBreakdownItem]
