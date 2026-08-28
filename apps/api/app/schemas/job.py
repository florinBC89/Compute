"""Jobs: orchestration state for one consumer-workspace research task
(V0.2 human-workspace slice)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

JobStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]


class JobCreateRequest(BaseModel):
    task_text: str
    model_preference: str | None = None


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    task_text: str
    current_step: str | None = None
    error_message: str | None = None
    spent_usd: float
    cost_cap_usd: float
    run_id: str | None = None


class JobEventItem(BaseModel):
    id: int
    event_type: str
    payload: dict[str, Any]
    created_at: str
