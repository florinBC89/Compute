"""Job-state helpers shared by the poll loop (app.worker) and the pipeline
it runs (app.agent.pipeline) -- kept in their own module so neither imports
the other.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Job, JobEvent

__all__ = [
    "JobCancelled",
    "CostCapReached",
    "emit",
    "is_still_running",
    "add_spend",
    "set_current_step",
]


class JobCancelled(Exception):
    """The job's status was set to CANCELLED externally (see routes.jobs).

    Deliberately not asyncio.CancelledError: that type has its own meaning
    for real task cancellation (e.g. worker process shutdown), and catching
    it broadly here would risk swallowing that too.
    """


class CostCapReached(Exception):
    """jobs.spent_usd has reached jobs.cost_cap_usd."""


async def emit(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
    event_type: str,
    payload: dict | None = None,
) -> None:
    async with session_factory() as session:
        session.add(JobEvent(job_id=job_id, event_type=event_type, payload=payload or {}))
        await session.commit()


async def is_still_running(
    session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID
) -> bool:
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        return job is not None and job.status == "RUNNING"


async def add_spend(
    session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID, cost_usd: float
) -> None:
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        job.spent_usd = float(job.spent_usd) + cost_usd
        await session.commit()


async def set_current_step(
    session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID, step: str | None
) -> None:
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        job.current_step = step
        await session.commit()


async def guard(
    session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID
) -> None:
    """Raise if the job was cancelled externally or the cost cap is reached.

    Call this before every step that would incur real spend -- it's the
    only place either condition is enforced, so every pipeline step gets
    both checks for free just by calling it first.
    """
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        if job is None or job.status != "RUNNING":
            raise JobCancelled()
        if float(job.spent_usd) >= float(job.cost_cap_usd):
            raise CostCapReached()
