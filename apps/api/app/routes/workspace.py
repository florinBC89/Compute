"""Workspace-scoped project/run views for the human workspace (V0.2 slice).

Parallel to the developer dashboard's project-slug/API-key-scoped routes
(app.routes.metrics, app.routes.runs) -- same underlying queries
(app.services.artifacts, app.services.runs), so the two surfaces can never
quietly report different numbers for the same data. These routes are keyed
by the concrete project_id/run_id the workspace app already has from its
own URL, and authorized by ownership (workspace_id match) rather than a
project-slug header: the consumer app isn't juggling multiple projects
behind one shared API key, so that header's indirection doesn't apply here.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Project, Run
from app.schemas.cross_model import PreviewModelSwitchRequest, PreviewModelSwitchResponse
from app.schemas.job import JobList
from app.schemas.metrics import ArtifactListResponse
from app.schemas.run import RunGraph, RunSummary
from app.services.artifacts import artifact_list_item, list_project_artifacts
from app.services.cross_model import build_preview
from app.services.jobs import list_project_jobs, to_job_response
from app.services.runs import run_graph_data, run_totals
from app.services.scope import Scope
from app.services.user_scope import CurrentUser, resolve_current_user

router = APIRouter(prefix="/workspace", tags=["workspace"])


async def _owned_project(
    session: AsyncSession, project_id: uuid.UUID, current_user: CurrentUser
) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.workspace_id != current_user.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        )
    return project


async def _owned_run(
    session: AsyncSession, run_id: uuid.UUID, current_user: CurrentUser
) -> Run:
    run = await session.get(Run, run_id)
    if run is None or run.workspace_id != current_user.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="run not found"
        )
    return run


@router.get("/projects/{project_id}/artifacts", response_model=ArtifactListResponse)
async def workspace_project_artifacts(
    project_id: uuid.UUID,
    artifact_type: str | None = None,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> ArtifactListResponse:
    """Backs the workspace app's project view -- the artifact tree grouped
    by type on the client side."""
    await _owned_project(session, project_id, current_user)
    rows = await list_project_artifacts(session, project_id, artifact_type)
    return ArtifactListResponse(artifacts=[artifact_list_item(row) for row in rows])


@router.get("/projects/{project_id}/jobs", response_model=JobList)
async def workspace_project_jobs(
    project_id: uuid.UUID,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobList:
    """Backs the workspace app's chat thread (V0.3 Phase 0): a project's
    turn history, oldest first. See app.services.jobs.list_project_jobs --
    "Job-as-turn": no separate messages table, a turn IS a Job.
    """
    project = await _owned_project(session, project_id, current_user)
    jobs = await list_project_jobs(session, project_id)
    return JobList(jobs=[to_job_response(job, project.name) for job in jobs])


@router.get("/runs/{run_id}", response_model=RunSummary)
async def workspace_run_summary(
    run_id: uuid.UUID,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> RunSummary:
    """Backs the workspace app's result screen (paid/avoided/tokens)."""
    run = await _owned_run(session, run_id, current_user)
    return RunSummary(
        id=str(run.id), status=run.status, **(await run_totals(session, run_id))
    )


@router.get("/runs/{run_id}/graph", response_model=RunGraph)
async def workspace_run_graph(
    run_id: uuid.UUID,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> RunGraph:
    """Backs the result screen's "View details" trace view."""
    await _owned_run(session, run_id, current_user)
    return RunGraph(**(await run_graph_data(session, run_id)))


@router.post(
    "/runs/{run_id}/preview-model-switch", response_model=PreviewModelSwitchResponse
)
async def workspace_preview_model_switch(
    run_id: uuid.UUID,
    body: PreviewModelSwitchRequest,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> PreviewModelSwitchResponse:
    """Backs the workspace app's "Switch model" screen -- what would carry
    over before actually executing anything with a different model (spec
    section 4). No `X-ComputeLayer-Project` header needed: the run's own
    `project_id` is enough scope for this one-shot evaluation.
    """
    run = await _owned_run(session, run_id, current_user)
    scope = Scope(
        workspace_id=current_user.workspace_id,
        project_id=run.project_id,
        project_slug="",
        api_key_id=None,
    )
    return await build_preview(session, scope, run_id, body.target_model)
