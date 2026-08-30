"""Acc response building + Work derivation (Agent OS V0.4 slice).

An Acc's "Work" is not stored -- it's its Project's existing Jobs
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

from app.models import Acc
from app.schemas.acc import AccResponse, AccWorkItem, WorkReuseLabel
from app.services.jobs import list_project_jobs
from app.services.runs import run_totals

__all__ = ["to_acc_response", "list_workspace_accs", "acc_work_items"]


def to_acc_response(acc: Acc, project_name: str) -> AccResponse:
    return AccResponse(
        id=str(acc.id),
        name=acc.name,
        goal=acc.goal,
        status=acc.status,
        project_id=str(acc.project_id),
        project_name=project_name,
        created_at=acc.created_at.isoformat(),
    )


async def list_workspace_accs(session: AsyncSession, workspace_id: uuid.UUID) -> list[Acc]:
    statement = (
        select(Acc)
        .where(Acc.workspace_id == workspace_id)
        .order_by(Acc.created_at.desc())
    )
    return list((await session.execute(statement)).scalars().all())


def _reuse_label(totals: dict) -> WorkReuseLabel:
    if totals["hits"] > 0 and totals["misses"] == 0:
        return "reused"
    if totals["hits"] > 0:
        return "partially_reused"
    return "fresh"


async def acc_work_items(session: AsyncSession, project_id: uuid.UUID) -> list[AccWorkItem]:
    jobs = await list_project_jobs(session, project_id)
    items: list[AccWorkItem] = []
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
            AccWorkItem(
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
