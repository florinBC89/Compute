"""Ethical response building + Work derivation (Agent OS V0.4 slice).

An Ethical's "Work" is not stored -- it's its Project's existing Jobs
(app.services.jobs.list_project_jobs), each labeled reused/partially
reused/fresh from the same run totals (app.services.runs.run_totals) the
workspace result screen already computes. Reusing both rather than adding
a parallel query keeps this from quietly reporting different numbers than
the result screen for the same run.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ethical
from app.schemas.ethical import EthicalResponse, EthicalWorkItem, WorkReuseLabel
from app.services.jobs import list_project_jobs
from app.services.runs import run_totals

__all__ = ["to_ethical_response", "list_workspace_ethicals", "ethical_work_items"]


def to_ethical_response(ethical: Ethical, project_name: str) -> EthicalResponse:
    return EthicalResponse(
        id=str(ethical.id),
        name=ethical.name,
        goal=ethical.goal,
        status=ethical.status,
        project_id=str(ethical.project_id),
        project_name=project_name,
        created_at=ethical.created_at.isoformat(),
    )


async def list_workspace_ethicals(session: AsyncSession, workspace_id: uuid.UUID) -> list[Ethical]:
    statement = (
        select(Ethical)
        .where(Ethical.workspace_id == workspace_id)
        .order_by(Ethical.created_at.desc())
    )
    return list((await session.execute(statement)).scalars().all())


def _reuse_label(totals: dict) -> WorkReuseLabel:
    if totals["hits"] > 0 and totals["misses"] == 0:
        return "reused"
    if totals["hits"] > 0:
        return "partially_reused"
    return "fresh"


async def ethical_work_items(session: AsyncSession, project_id: uuid.UUID) -> list[EthicalWorkItem]:
    jobs = await list_project_jobs(session, project_id)
    items: list[EthicalWorkItem] = []
    for job in jobs:
        cost_usd = 0.0
        saved_usd = 0.0
        reuse_label: WorkReuseLabel | None = None
        if job.run_id is not None:
            totals = await run_totals(session, job.run_id)
            cost_usd = totals["total_cost_usd"]
            saved_usd = totals["saved_usd"]
            reuse_label = _reuse_label(totals)
        items.append(
            EthicalWorkItem(
                job_id=str(job.id),
                task_text=job.task_text,
                status=job.status,
                reuse_label=reuse_label,
                cost_usd=cost_usd,
                saved_usd=saved_usd,
                created_at=job.created_at.isoformat(),
            )
        )
    return items
