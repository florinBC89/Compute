"""Turn-execution helpers shared by every path that runs a `cl.compute.run()`
call against this process's own API and needs to track that against a `Job`
row -- today only app.agent.pipeline (the six-step research pipeline), soon
also the single-call chat-turn path described in the V0.3 chat component
spec. Nothing here is pipeline-specific: no step names, no research-domain
prompts, no six-step topology -- just the provisioning, cancellation-racing,
provider-resolution and job-state bookkeeping any turn needs regardless of
how many `cl.compute.run()` calls it makes.

Deliberately mirrors app.agent.job_control's own module docstring: this
module MAY import job_control (guard/emit/add_spend/is_still_running are
exactly the primitives a turn needs), but must NEVER import
app.agent.pipeline -- pipeline.py imports *this* module, and the reverse
would be a cycle. Keep it that way.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import Any, Awaitable, Callable

from computelayer import ComputeLayer
from computelayer.context import collect_metrics
from computelayer.pricing import estimate_cost
from computelayer.result import ComputeResult
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent import job_control
from app.agent.job_control import JobCancelled
from app.agent.providers import anthropic as anthropic_provider
from app.agent.providers import gemini as gemini_provider
from app.agent.providers import openai as openai_provider
from app.models import ApiKey, Job, Project
from app.models.base import utcnow
from app.services.scope import KEY_PREFIX_LENGTH, generate_api_key, hash_api_key

__all__ = [
    "PROVIDER_MODULES",
    "DEFAULT_PROVIDER",
    "provision_internal_key",
    "deactivate_key",
    "project_slug",
    "set_run_id",
    "watch_for_cancellation",
    "resolve_provider",
    "run_computation",
    "mark_failed",
    "maybe_title_project",
]

#: job.model_preference -> provider module. Unset or unrecognized falls back
#: to DEFAULT_PROVIDER -- today's only choice before Phase 9, and still the
#: safe default once there are three.
#:
#: Resolved to a *module*, not a `(complete_fn, MODEL)` tuple captured at
#: import time: a captured function reference silently stops following
#: `monkeypatch.setattr(openai_provider, "complete", ...)` in tests (the
#: patch changes the module's attribute; a tuple built once at import time
#: already has a copy of the *old* value) -- exactly the class of bug that
#: let a cost-cap test call the real OpenAI API instead of the fixture's
#: mock. Looking up `.complete`/`.MODEL` on the module fresh in
#: `resolve_provider` is what keeps monkeypatching working.
PROVIDER_MODULES = {
    "openai": openai_provider,
    "anthropic": anthropic_provider,
    "gemini": gemini_provider,
}
DEFAULT_PROVIDER = "openai"

#: How often watch_for_cancellation re-checks whether the job is still
#: RUNNING while a computation is actually in flight (Phase 10). Cheap
#: enough to poll frequently: it only runs for the duration of one
#: computation, not the whole job.
CANCELLATION_POLL_SECONDS = 0.5

#: V0.3 conversation history: the short AI-generated conversation title
#: (create_job's plain-truncated-text fallback is what shows until this
#: replaces it -- see maybe_title_project).
TITLE_SYSTEM = (
    "Summarize the user's request in 2-4 words as a short conversation "
    "title. No punctuation, no quotes, no trailing period. Reply with "
    "just the title."
)
TITLE_MAX_TOKENS = 12


async def provision_internal_key(
    session_factory: async_sessionmaker[AsyncSession],
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """A fresh, single-job API key -- consistent with how every other API
    key in this system works (plaintext known only at creation; see
    app.provision's identical reasoning for invite keys). Deactivated by the
    caller once the job/turn is done, so it can't be reused even if it
    somehow leaked.
    """
    plaintext = generate_api_key("live")
    api_key_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            ApiKey(
                id=api_key_id,
                workspace_id=workspace_id,
                project_id=project_id,
                name="internal worker (one job)",
                key_prefix=plaintext[:KEY_PREFIX_LENGTH],
                key_hash=hash_api_key(plaintext),
            )
        )
        await session.commit()
    return plaintext, api_key_id


async def deactivate_key(
    session_factory: async_sessionmaker[AsyncSession], api_key_id: uuid.UUID
) -> None:
    async with session_factory() as session:
        api_key = await session.get(ApiKey, api_key_id)
        if api_key is not None:
            api_key.active = False
            await session.commit()


async def project_slug(
    session_factory: async_sessionmaker[AsyncSession], project_id: uuid.UUID
) -> str:
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        return project.slug


async def set_run_id(
    session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID, run_id: str
) -> None:
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        job.run_id = uuid.UUID(run_id)
        await session.commit()


async def watch_for_cancellation(
    session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID
) -> None:
    """Polls until the job is no longer RUNNING. Raced against an in-flight
    computation in run_computation (Phase 10) so a Cancel click actually
    interrupts a slow/hung provider call instead of waiting for it to finish
    or time out on its own -- before this, `job_control.guard()`'s pre-step
    check meant cancellation only took effect at the *next* step boundary,
    so a single stuck provider call could make Cancel silently do nothing
    for as long as that call kept running.
    """
    while await job_control.is_still_running(session_factory, job_id):
        await asyncio.sleep(CANCELLATION_POLL_SECONDS)


async def run_computation(
    cl: ComputeLayer,
    session_factory: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
    *,
    name: str,
    inputs: dict,
    fn: Callable[[], Awaitable[Any]],
    model: str | None = None,
    artifact_type: str | None,
    ttl: int | None = None,
    cross_model_reuse: bool = True,
    emit_events: bool = True,
) -> ComputeResult:
    """Runs one `cl.compute.run()` call, racing it against
    watch_for_cancellation so a Cancel click interrupts even a hung provider
    call. `emit_events=False` skips the STEP_STARTED/STEP_FINISHED JobEvents
    and the current-step bookkeeping -- for a single-call chat turn, where
    there's no multi-step progress to report and no "current step" to track.
    """
    await job_control.guard(session_factory, job_id)
    if emit_events:
        await job_control.set_current_step(session_factory, job_id, name)
        await job_control.emit(session_factory, job_id, "STEP_STARTED", {"step": name})

    step_task = asyncio.create_task(
        cl.compute.run(
            name=name,
            inputs=inputs,
            fn=fn,
            model=model,
            artifact_type=artifact_type,
            cross_model_reuse=cross_model_reuse,
            ttl=ttl,
        )
    )
    watch_task = asyncio.create_task(watch_for_cancellation(session_factory, job_id))
    try:
        done, _ = await asyncio.wait(
            {step_task, watch_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if step_task not in done:
            # Cancelled mid-call: stop waiting on the provider rather than
            # letting it run to completion. Cancelling step_task throws
            # CancelledError into cl.compute.run() at its current await
            # point; Compute.run()'s own `except BaseException` handler
            # records the computation as FAILED and releases the stampede
            # lock before that propagates here.
            step_task.cancel()
            with contextlib.suppress(BaseException):
                await step_task
            raise JobCancelled()
        result = step_task.result()
    finally:
        watch_task.cancel()
        with contextlib.suppress(BaseException):
            await watch_task

    if result.cost_usd:
        await job_control.add_spend(session_factory, job_id, result.cost_usd)
    if emit_events:
        await job_control.emit(
            session_factory, job_id, "STEP_FINISHED", {"step": name, "cost_usd": result.cost_usd}
        )
    return result


def resolve_provider(model_preference: str | None) -> tuple[Callable[..., Awaitable[str]], str]:
    module = PROVIDER_MODULES.get(model_preference or "", PROVIDER_MODULES[DEFAULT_PROVIDER])
    return module.complete, module.MODEL


async def mark_failed(
    session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID, reason: str
) -> None:
    """If the job is still RUNNING, marks it FAILED with `reason`. Does NOT
    emit a JobEvent -- callers that want one (e.g. run_research_pipeline's
    cost-cap handling) emit it themselves right after calling this, since a
    parallel chat-turn execution path needs this state transition without
    that side effect.
    """
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        if job.status == "RUNNING":
            job.status = "FAILED"
            job.error_message = reason
            job.finished_at = utcnow()
            await session.commit()


async def maybe_title_project(
    session_factory: async_sessionmaker[AsyncSession],
    job: Job,
    *,
    on_titled: Callable[[str], Awaitable[None]] | None = None,
) -> None:
    """V0.3 conversation history: the first job in a project gets an
    AI-generated title, replacing create_job's plain-truncated-text
    fallback. Meant to be launched as a fire-and-forget asyncio.create_task
    by the caller -- doesn't gate the caller's own progress, and only ever
    runs once per project (the cheap COUNT check below).

    Deliberately NOT wrapped in cl.compute.run(): a title has no future
    reuse value (each project's first message is unique by definition), so
    there's nothing the reuse engine would ever do with it -- it's a plain,
    uninstrumented call, with its own small cost added to job.spent_usd
    directly for honest accounting.

    `on_titled`, if given, is awaited right after the PROJECT_TITLED event
    is emitted -- a hook for a chat-turn caller that wants to push the new
    title to a connected client, without job_control's own JobEvent-based
    fan-out.
    """
    async with session_factory() as session:
        count = (
            await session.execute(
                select(func.count())
                .select_from(Job)
                .where(Job.project_id == job.project_id)
            )
        ).scalar_one()
    if count != 1:
        return  # not this project's first job -- already titled

    try:
        with collect_metrics() as metrics:
            title = await openai_provider.complete(
                system=TITLE_SYSTEM, prompt=job.task_text, max_tokens=TITLE_MAX_TOKENS
            )
    except Exception:
        return  # a failed title generation should never surface as a job failure

    title = title.strip().strip('"').strip("'").rstrip(".")
    if not title:
        return

    cost_usd = metrics.cost_usd or estimate_cost(
        openai_provider.MODEL, metrics.input_tokens, metrics.output_tokens
    )

    async with session_factory() as session:
        project = await session.get(Project, job.project_id)
        if project is not None:
            project.name = title
            await session.commit()

    if cost_usd:
        await job_control.add_spend(session_factory, job.id, cost_usd)
    await job_control.emit(session_factory, job.id, "PROJECT_TITLED", {"name": title})
    if on_titled is not None:
        await on_titled(title)
