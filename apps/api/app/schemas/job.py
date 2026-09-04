"""Jobs: orchestration state for one consumer-workspace research task
(V0.2 human-workspace slice)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

JobStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]


class JobCreateRequest(BaseModel):
    task_text: str
    model_preference: str | None = None
    #: V0.3 conversation history: attach this turn to an existing
    #: conversation (Project). Omitted/None -> a brand-new conversation is
    #: created for it. See app.routes.jobs.create_job.
    project_id: str | None = None
    #: "Lazy" mode: appends a code-minimalism ruleset to this turn's system
    #: prompt (see app.agent.chat.LAZY_MODE_SYSTEM_SUFFIX). Off by default.
    lazy_mode: bool = False


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    task_text: str
    #: The clean assistant-facing reply (V0.3 chat turn) -- None until the
    #: job SUCCEEDS. See app.services.jobs.to_job_response.
    answer_text: str | None = None
    current_step: str | None = None
    error_message: str | None = None
    spent_usd: float
    cost_cap_usd: float
    run_id: str | None = None
    project_id: str
    #: The conversation's current title (V0.3) -- a fallback (truncated
    #: task_text) until the async AI-generated title replaces it; see the
    #: PROJECT_TITLED job_event for the live update.
    project_name: str
    lazy_mode: bool = False


class JobList(BaseModel):
    """A project's turn history, oldest first -- the conversation itself
    (V0.3): no separate messages table, a turn IS a Job. See
    app.services.jobs.list_project_jobs.
    """

    jobs: list[JobResponse]


class JobEventItem(BaseModel):
    id: int
    event_type: str
    payload: dict[str, Any]
    created_at: str
