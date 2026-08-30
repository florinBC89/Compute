"""Jobs: submit and track one consumer-workspace research task (V0.2 human
workspace, Phase 3).

Unlike `runs`/`computations`, which are driven by whatever process holds an
API key and calls the SDK step by step, a job is the server-side unit of
work: `app.worker` picks up QUEUED jobs and runs the research pipeline
itself, emitting `job_events` as it goes. `GET /{id}/events` streams those
over SSE so the workspace app can show live progress without polling.
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.config import get_settings
from app.db import get_session, get_sessionmaker
from app.models import Job, JobEvent, Project
from app.models.base import utcnow
from app.schemas.job import JobCreateRequest, JobEventItem, JobResponse
from app.services.jobs import to_job_response
from app.services.user_scope import CurrentUser, resolve_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])

TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}
SSE_POLL_INTERVAL_SECONDS = 0.5

#: Truncated to this length as the immediate fallback conversation title --
#: replaced by the AI-generated one (app.agent.pipeline._maybe_title_project)
#: once that completes, usually within a couple seconds.
FALLBACK_TITLE_LENGTH = 40


async def _resolve_or_create_project(
    session: AsyncSession, workspace_id: uuid.UUID, project_id: str | None, task_text: str
) -> Project:
    """V0.3 conversation history: a conversation IS a Project. An explicit
    `project_id` attaches this turn to an existing conversation (ownership
    verified); omitted, a brand-new one is created -- this is what makes
    the workspace app's "New" and its per-conversation history both work
    without any project-management UI of their own.
    """
    if project_id:
        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
            ) from exc
        project = await session.get(Project, project_uuid)
        if project is None or project.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
            )
        return project

    project = Project(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        name=task_text[:FALLBACK_TITLE_LENGTH].strip(),
        slug=f"conv-{uuid.uuid4().hex[:12]}",
    )
    session.add(project)
    await session.flush()
    return project


async def _get_owned_job(
    session: AsyncSession, job_id: str, current_user: CurrentUser
) -> Job:
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="job not found"
        ) from exc

    job = await session.get(Job, job_uuid)
    if job is None or job.workspace_id != current_user.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="job not found"
        )
    return job


@router.post("", response_model=JobResponse)
async def create_job(
    body: JobCreateRequest,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    if not body.task_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="task_text is required"
        )

    task_text = body.task_text.strip()
    project = await _resolve_or_create_project(
        session, current_user.workspace_id, body.project_id, task_text
    )
    settings = get_settings()

    job = Job(
        id=uuid.uuid4(),
        workspace_id=current_user.workspace_id,
        project_id=project.id,
        user_id=current_user.user_id,
        task_text=task_text,
        model_preference=body.model_preference,
        cost_cap_usd=settings.default_job_cost_cap_usd,
    )
    session.add(job)
    await session.flush()
    session.add(JobEvent(job_id=job.id, event_type="QUEUED", payload={}))
    return to_job_response(job, project.name)


async def _project_name(session: AsyncSession, project_id: uuid.UUID) -> str:
    project = await session.get(Project, project_id)
    return project.name if project is not None else ""


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    job = await _get_owned_job(session, job_id, current_user)
    return to_job_response(job, await _project_name(session, job.project_id))


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    """Mark a job CANCELLED. For a QUEUED job this is final immediately --
    the worker never picks it up. For a RUNNING job, the pipeline itself
    watches `status` for the duration of the step currently in flight (see
    app.agent.pipeline._watch_for_cancellation), so this interrupts even a
    slow/hung provider call rather than only taking effect at the next step
    boundary; it never overwrites this back to SUCCEEDED/FAILED once it
    sees it's no longer RUNNING. No separate "cancel requested" flag is
    needed.
    """
    job = await _get_owned_job(session, job_id, current_user)
    if job.status in ("QUEUED", "RUNNING"):
        job.status = "CANCELLED"
        job.finished_at = utcnow()
        session.add(JobEvent(job_id=job.id, event_type="CANCELLED", payload={}))
    return to_job_response(job, await _project_name(session, job.project_id))


@router.get("/{job_id}/events")
async def stream_job_events(
    job_id: str,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    # Ownership check up front using the request-scoped session -- the
    # generator below opens its own short-lived sessions per poll instead of
    # holding this one across a stream that can run for minutes.
    job = await _get_owned_job(session, job_id, current_user)
    session_factory = get_sessionmaker()

    async def event_stream():
        last_id = 0
        while True:
            async with session_factory() as poll_session:
                rows = (
                    (
                        await poll_session.execute(
                            select(JobEvent)
                            .where(JobEvent.job_id == job.id, JobEvent.id > last_id)
                            .order_by(JobEvent.id)
                        )
                    )
                    .scalars()
                    .all()
                )
                current_job = await poll_session.get(Job, job.id)

            for row in rows:
                last_id = row.id
                item = JobEventItem(
                    id=row.id,
                    event_type=row.event_type,
                    payload=row.payload,
                    created_at=row.created_at.isoformat(),
                )
                yield f"data: {item.model_dump_json()}\n\n"

            if current_job is not None and current_job.status in TERMINAL_STATUSES:
                return
            await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
