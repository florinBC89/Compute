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

__all__ = ["to_job_response", "list_project_jobs"]


def to_job_response(job: Job) -> JobResponse:
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
    )


async def list_project_jobs(session: AsyncSession, project_id: uuid.UUID) -> list[Job]:
    """A project's turn history, oldest first -- the conversation itself
    (V0.3 "Job-as-turn": no separate messages table, a turn IS a Job),
    ordered chronologically the way a chat thread reads top to bottom.
    """
    statement = select(Job).where(Job.project_id == project_id).order_by(Job.created_at)
    return list((await session.execute(statement)).scalars().all())
