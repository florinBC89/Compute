"""Run endpoints (spec §34, §35)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RunCreateBody(BaseModel):
    external_run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunCreateResponse(BaseModel):
    id: str


class RunFinishBody(BaseModel):
    status: Literal["SUCCEEDED", "FAILED"] = "SUCCEEDED"


class RunSummary(BaseModel):
    id: str
    status: str
    computations: int
    hits: int
    misses: int
    stale: int
    forced: int
    total_cost_usd: float
    saved_usd: float
    input_tokens: int
    output_tokens: int


class RunListItem(RunSummary):
    external_run_id: str | None = None
    started_at: str
    finished_at: str | None = None


class RunList(BaseModel):
    runs: list[RunListItem]


class GraphNode(BaseModel):
    id: str
    name: str
    status: str
    cost_usd: float
    saved_usd: float
    latency_ms: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class GraphEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    key: str

    model_config = {"populate_by_name": True}


class RunGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
