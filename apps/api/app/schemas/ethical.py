"""Ethical: a persistent named agent identity (Agent OS V0.4 slice)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

EthicalStatus = Literal["active", "archived"]
WorkReuseLabel = Literal["reused", "partially_reused", "fresh"]


class EthicalCreateRequest(BaseModel):
    name: str
    goal: str | None = None
    project_id: str


class EthicalPatchRequest(BaseModel):
    name: str | None = None
    goal: str | None = None


class EthicalResponse(BaseModel):
    id: str
    name: str
    goal: str | None = None
    status: EthicalStatus
    project_id: str
    project_name: str
    created_at: str


class EthicalList(BaseModel):
    ethicals: list[EthicalResponse]


class EthicalWorkItem(BaseModel):
    job_id: str
    task_text: str
    status: str
    #: None for jobs with no run_id yet (queued/running) -- there's nothing
    #: to classify as reused or fresh until a run has actually executed.
    reuse_label: WorkReuseLabel | None = None
    cost_usd: float
    saved_usd: float
    created_at: str


class EthicalDetail(EthicalResponse):
    work: list[EthicalWorkItem]
