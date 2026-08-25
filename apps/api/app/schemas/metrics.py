"""Project metrics (spec §36)."""

from __future__ import annotations

from pydantic import BaseModel


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
