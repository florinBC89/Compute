"""Job worker (V0.2 human-workspace slice, Phase 3).

    python -m app.worker

Polls `jobs` for the oldest QUEUED row with `FOR UPDATE SKIP LOCKED` --
chosen over a task-queue library because today's Redis
(app.services.locks) is deliberately best-effort/no-op-on-failure, the
wrong reliability posture for job dispatch, while Postgres is already this
system's reliable source of truth. `SKIP LOCKED` is what makes running more
than one worker later a non-breaking change: each worker simply skips rows
another one already has locked, no extra coordination needed.

This module runs a *stub* pipeline (Phase 3 scope): three fixed steps with
no real work behind them, proving the queue/worker/SSE-events plumbing end
to end before Phase 4 adds the real provider-calling pipeline behind the
same `run_pipeline` seam.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import Job, JobEvent
from app.models.base import utcnow

logger = logging.getLogger("computelayer.worker")

POLL_INTERVAL_SECONDS = 1.0
STEP_DURATION_SECONDS = 2.0

#: Phase 4 replaces this with app.agent.pipeline.run_research_pipeline,
#: which performs these same named steps for real and additionally checks
#: the cost cap between them -- the queue/SSE/cancellation machinery around
#: it does not change.
STUB_STEPS = ("search_sources", "extract_facts", "write_draft")


async def _emit(
    session_factory: async_sessionmaker[AsyncSession],
    job_id,
    event_type: str,
    payload: dict | None = None,
) -> None:
    async with session_factory() as session:
        session.add(JobEvent(job_id=job_id, event_type=event_type, payload=payload or {}))
        await session.commit()


async def _is_still_running(
    session_factory: async_sessionmaker[AsyncSession], job_id
) -> bool:
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        return job is not None and job.status == "RUNNING"


async def _claim_next_job(
    session_factory: async_sessionmaker[AsyncSession],
) -> Job | None:
    async with session_factory() as session:
        statement = (
            select(Job)
            .where(Job.status == "QUEUED")
            .order_by(Job.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = (await session.execute(statement)).scalars().first()
        if job is None:
            return None
        job.status = "RUNNING"
        job.started_at = utcnow()
        await session.commit()
        return job


async def run_stub_pipeline(
    session_factory: async_sessionmaker[AsyncSession], job: Job
) -> None:
    await _emit(session_factory, job.id, "STARTED")

    for step in STUB_STEPS:
        if not await _is_still_running(session_factory, job.id):
            logger.info("job %s no longer RUNNING -- stopping", job.id)
            return

        async with session_factory() as session:
            live_job = await session.get(Job, job.id)
            live_job.current_step = step
            await session.commit()
        await _emit(session_factory, job.id, "STEP_STARTED", {"step": step})

        await asyncio.sleep(STEP_DURATION_SECONDS)

        await _emit(session_factory, job.id, "STEP_FINISHED", {"step": step})

    async with session_factory() as session:
        live_job = await session.get(Job, job.id)
        if live_job.status != "RUNNING":
            # Cancelled during the last step's sleep.
            return
        live_job.status = "SUCCEEDED"
        live_job.current_step = None
        live_job.finished_at = utcnow()
        await session.commit()
    await _emit(session_factory, job.id, "SUCCEEDED")


async def _run_one(session_factory: async_sessionmaker[AsyncSession], job: Job) -> None:
    try:
        await run_stub_pipeline(session_factory, job)
    except Exception:
        logger.exception("job %s failed", job.id)
        async with session_factory() as session:
            live_job = await session.get(Job, job.id)
            if live_job is not None and live_job.status == "RUNNING":
                live_job.status = "FAILED"
                live_job.error_message = "internal error"
                live_job.finished_at = utcnow()
                await session.commit()
        await _emit(session_factory, job.id, "FAILED")


async def worker_loop() -> None:
    get_settings()  # fail fast on missing/invalid config before polling
    session_factory = get_sessionmaker()
    logger.info("worker started, polling every %ss", POLL_INTERVAL_SECONDS)

    while True:
        job = await _claim_next_job(session_factory)
        if job is None:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue
        logger.info("claimed job %s: %r", job.id, job.task_text)
        await _run_one(session_factory, job)


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(worker_loop())
