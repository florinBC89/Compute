"""Shared job-response building + turn-history listing (V0.2 Phase 3,
V0.3 Phase 0).

`app.routes.jobs` (create/get/cancel a job) and the workspace turn-history
route both need the exact same `JobResponse` shape and the exact same
"what is this project's conversation" query -- pulled out here so the two
call sites can't quietly drift, the same reasoning `app.services.artifacts`
and `app.services.runs` already document for the developer-dashboard vs
workspace split.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job
from app.schemas.job import JobResponse

__all__ = ["to_job_response", "list_project_jobs", "build_chat_history"]


def to_job_response(job: Job, project_name: str) -> JobResponse:
    """`project_name` is passed explicitly rather than read off a `Job.project`
    relationship -- this codebase fetches related rows via separate queries
    throughout (see app.services.artifacts/runs), not ORM relationships, and
    every caller already has the project in hand (or fetches it once for a
    whole list of jobs, e.g. app.routes.workspace.workspace_project_jobs)."""
    return JobResponse(
        id=str(job.id),
        status=job.status,
        task_text=job.task_text,
        answer_text=job.answer_text,
        current_step=job.current_step,
        error_message=job.error_message,
        spent_usd=float(job.spent_usd),
        cost_cap_usd=float(job.cost_cap_usd),
        run_id=str(job.run_id) if job.run_id else None,
        project_id=str(job.project_id),
        project_name=project_name,
        lazy_mode=job.lazy_mode,
    )


async def list_project_jobs(session: AsyncSession, project_id: uuid.UUID) -> list[Job]:
    """A project's turn history, oldest first -- the conversation itself
    (V0.3 "Job-as-turn": no separate messages table, a turn IS a Job),
    ordered chronologically the way a chat thread reads top to bottom.
    """
    statement = select(Job).where(Job.project_id == project_id).order_by(Job.created_at)
    return list((await session.execute(statement)).scalars().all())


async def build_chat_history(
    session: AsyncSession, project_id: uuid.UUID, *, before_job_id: uuid.UUID | None = None
) -> list[dict[str, str]]:
    """Turn a project's Jobs into a role/content transcript for the chat-turn
    `compute.run()` fingerprint.

    Only SUCCEEDED jobs with a non-empty `answer_text` contribute turns.
    Excluding everything else -- QUEUED/RUNNING/CANCELLED, FAILED, and the
    degenerate SUCCEEDED-but-empty-answer case -- is what makes regenerating
    the *same* message a guaranteed cache hit: a failed job leaves no slot in
    the history, so it's absent from the fingerprint of every later
    `compute.run()` call, and regenerating right after a failure naturally
    computes fresh inputs (a real retry, correctly a cache MISS). Regenerating
    a message whose prior attempt *succeeded*, on the other hand, walks the
    exact same surviving history and reproduces a byte-identical fingerprint,
    so it's served straight from cache instead of re-spending on the LLM.
    """
    jobs = await list_project_jobs(session, project_id)
    history: list[dict[str, str]] = []
    for job in jobs:
        if before_job_id is not None and job.id == before_job_id:
            break
        if job.status != "SUCCEEDED" or not job.answer_text:
            continue
        history.append({"role": "user", "content": job.task_text})
        history.append({"role": "assistant", "content": job.answer_text})
    return history
