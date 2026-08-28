"""Job worker (V0.2 human-workspace slice).

    python -m app.worker

Polls `jobs` for the oldest QUEUED row with `FOR UPDATE SKIP LOCKED` --
chosen over a task-queue library because today's Redis
(app.services.locks) is deliberately best-effort/no-op-on-failure, the
wrong reliability posture for job dispatch, while Postgres is already this
system's reliable source of truth. `SKIP LOCKED` is what makes running more
than one worker later a non-breaking change: each worker simply skips rows
another one already has locked, no extra coordination needed.

The actual research pipeline lives in app.agent.pipeline -- this module is
only the dispatch loop: claim a job, hand it to the pipeline, record a
failure if the pipeline raises something it didn't already handle itself
(cancellation and cost-cap breaches are handled inside the pipeline; this
is the catch-all for genuine errors, e.g. a provider outage).
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.pipeline import run_research_pipeline
from app.config import get_settings
from app.db import get_sessionmaker
from app.models import Job
from app.models.base import utcnow

logger = logging.getLogger("computelayer.worker")

POLL_INTERVAL_SECONDS = 1.0


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


async def _run_one(session_factory: async_sessionmaker[AsyncSession], job: Job) -> None:
    try:
        await run_research_pipeline(job, session_factory)
    except Exception:
        logger.exception("job %s failed", job.id)
        async with session_factory() as session:
            live_job = await session.get(Job, job.id)
            if live_job is not None and live_job.status == "RUNNING":
                live_job.status = "FAILED"
                live_job.error_message = "internal error"
                live_job.finished_at = utcnow()
                await session.commit()


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
