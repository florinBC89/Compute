"""Job worker (V0.2 human-workspace slice).

    python -m app.worker

Polls `jobs` for the oldest QUEUED row with `FOR UPDATE SKIP LOCKED` --
chosen over a task-queue library because today's Redis
(app.services.locks) is deliberately best-effort/no-op-on-failure, the
wrong reliability posture for job dispatch, while Postgres is already this
system's reliable source of truth. `SKIP LOCKED` is what makes running more
than one worker later a non-breaking change: each worker simply skips rows
another one already has locked, no extra coordination needed.

`worker_loop` (Phase 10) runs up to `settings.max_concurrent_jobs` jobs at
once in this one process, as plain asyncio tasks -- there's no per-step
blocking I/O outside of awaited HTTP calls, so real concurrency doesn't
need real threads/processes here. `_claim_next_job`'s per-workspace cap is
what stops one workspace queuing many jobs from claiming every concurrent
slot and starving every other workspace; claims themselves stay serialized
(the main loop only ever has one `_claim_next_job` call in flight), so
nothing races the running-jobs count that cap reads.

The actual research pipeline lives in app.agent.pipeline -- this module is
only the dispatch loop: claim a job, hand it to the pipeline, record a
failure if the pipeline raises something it didn't already handle itself
(cancellation, including mid-provider-call, and cost-cap breaches are
handled inside the pipeline; this is the catch-all for genuine errors,
classified into "provider unavailable" for a provider/network failure vs
"internal error" for anything else, since the two call for different user
messaging in apps/workspace).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import httpx
from anthropic import APIError as AnthropicAPIError
from google.genai.errors import APIError as GeminiAPIError
from openai import APIError as OpenAIAPIError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from app.agent.pipeline import run_research_pipeline
from app.config import get_settings
from app.db import get_sessionmaker
from app.models import Job
from app.models.base import utcnow

logger = logging.getLogger("computelayer.worker")

POLL_INTERVAL_SECONDS = 1.0

#: Real provider/network failures -- as opposed to a bug in this codebase --
#: get a distinct, more honest error_message (see _run_one) so apps/workspace
#: can tell a user "try again shortly" instead of a generic failure.
PROVIDER_ERRORS = (httpx.HTTPError, OpenAIAPIError, AnthropicAPIError, GeminiAPIError)


async def _claim_next_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    max_per_workspace: int | None = None,
) -> Job | None:
    async with session_factory() as session:
        statement = select(Job).where(Job.status == "QUEUED")

        if max_per_workspace is not None:
            running = aliased(Job)
            running_count = (
                select(func.count())
                .select_from(running)
                .where(running.workspace_id == Job.workspace_id, running.status == "RUNNING")
                .correlate(Job)
                .scalar_subquery()
            )
            statement = statement.where(running_count < max_per_workspace)

        statement = statement.order_by(Job.created_at).limit(1).with_for_update(skip_locked=True)
        job = (await session.execute(statement)).scalars().first()
        if job is None:
            return None
        job.status = "RUNNING"
        job.started_at = utcnow()
        await session.commit()
        return job


async def _mark_failed(
    session_factory: async_sessionmaker[AsyncSession], job_id: Any, message: str
) -> None:
    async with session_factory() as session:
        live_job = await session.get(Job, job_id)
        if live_job is not None and live_job.status == "RUNNING":
            live_job.status = "FAILED"
            live_job.error_message = message
            live_job.finished_at = utcnow()
            await session.commit()


async def _run_one(
    session_factory: async_sessionmaker[AsyncSession],
    job: Job,
    *,
    transport_factory: Callable[[str, str], Any] | None = None,
) -> None:
    try:
        await run_research_pipeline(job, session_factory, transport_factory=transport_factory)
    except PROVIDER_ERRORS:
        logger.exception("job %s failed: provider/network error", job.id)
        await _mark_failed(session_factory, job.id, "provider unavailable")
    except Exception:
        logger.exception("job %s failed", job.id)
        await _mark_failed(session_factory, job.id, "internal error")


async def worker_loop() -> None:
    settings = get_settings()  # fail fast on missing/invalid config before polling
    session_factory = get_sessionmaker()
    logger.info(
        "worker started, polling every %ss (max_concurrent_jobs=%s, "
        "max_concurrent_jobs_per_workspace=%s)",
        POLL_INTERVAL_SECONDS,
        settings.max_concurrent_jobs,
        settings.max_concurrent_jobs_per_workspace,
    )

    running: set[asyncio.Task] = set()
    while True:
        while len(running) < settings.max_concurrent_jobs:
            job = await _claim_next_job(
                session_factory, max_per_workspace=settings.max_concurrent_jobs_per_workspace
            )
            if job is None:
                break
            logger.info("claimed job %s: %r", job.id, job.task_text)
            running.add(asyncio.create_task(_run_one(session_factory, job)))

        if not running:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        _, running = await asyncio.wait(
            running, timeout=POLL_INTERVAL_SECONDS, return_when=asyncio.FIRST_COMPLETED
        )


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(worker_loop())
