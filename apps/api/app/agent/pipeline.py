"""The real research pipeline (V0.2 human workspace).

Six steps, each one `cl.compute.run()` call against this process's own API
(see app.config.Settings.internal_api_url) -- exactly the same reuse
engine, cost ledger and model-switch-preview endpoint a real SDK user gets,
with zero special-casing for "this call came from the worker." Passing an
upstream `ComputeResult` straight into a downstream step's `inputs` is what
auto-wires the dependency graph (see
`computelayer.compute.extract_compute_dependencies`) -- no manual
`dependencies=[]` needed, the same pattern `benchmarks/research-agent/
workflow.py` uses for its (fake) topology.

`search_sources` is the one non-LLM step (a Tavily call, no `model=` --
search results aren't tied to any model's identity, matching the spec's own
portability table: "Search results -- Portable -- Reuse when still fresh").
Every LLM step downstream resolves its own provider via
`_resolve_step_provider`: an explicit `job.model_preference` ("openai" /
"anthropic" / "gemini") picks one provider for the whole run, same as
Phase 7; `model_preference == "auto"` (Phase 9, the spec's own mockup
default) instead looks each step up in `AUTO_ROUTING`, a static
task-type -> provider table -- not a learned or dynamic router, matching
the spec's own framing ("Auto mode should *eventually* select...").

`search_sources` through `analyze` opt into cross-model reuse (portable,
provider-agnostic research); `write_draft` and `fact_check` do not -- the
spec's own model-switch example draws this exact line ("Claude only needs
to: Review relevant existing context, Perform the requested rewrite"): the
draft is specifically what the new model is being asked to write, and
reusing it verbatim would make a model switch free but pointless.
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

from app.agent import job_control, tavily
from app.agent.job_control import CostCapReached, JobCancelled
from app.agent.providers import anthropic as anthropic_provider
from app.agent.providers import gemini as gemini_provider
from app.agent.providers import openai as openai_provider
from app.config import get_settings
from app.models import ApiKey, Job, Project
from app.models.base import utcnow
from app.services.scope import KEY_PREFIX_LENGTH, generate_api_key, hash_api_key

__all__ = ["run_research_pipeline", "CostCapReached", "JobCancelled"]

#: job.model_preference -> provider module. Unset or unrecognized falls back
#: to DEFAULT_PROVIDER -- today's only choice before this phase, and still
#: the safe default once there are three.
#:
#: Resolved to a *module*, not a `(complete_fn, MODEL)` tuple captured at
#: import time: a captured function reference silently stops following
#: `monkeypatch.setattr(openai_provider, "complete", ...)` in tests (the
#: patch changes the module's attribute; a tuple built once at import time
#: already has a copy of the *old* value) -- exactly the class of bug that
#: let a cost-cap test call the real OpenAI API instead of the fixture's
#: mock. Looking up `.complete`/`.MODEL` on the module fresh in
#: `_resolve_provider` is what keeps monkeypatching working.
PROVIDER_MODULES = {
    "openai": openai_provider,
    "anthropic": anthropic_provider,
    "gemini": gemini_provider,
}
DEFAULT_PROVIDER = "openai"

#: The picker value that selects static per-step routing instead of one
#: provider for the whole run.
AUTO_PREFERENCE = "auto"

#: step name -> provider key, one entry per LLM step. Static and hardcoded
#: (not learned/dynamic) per the spec's own framing of Auto mode. Chosen so
#: an Auto run visibly touches more than one provider and costs less than
#: running the whole pipeline on the single strongest/priciest provider
#: (anthropic, today's most expensive of the three integrated models):
#: extraction and verification are cheap, mechanical tasks that don't need
#: the strongest model; analysis and the final draft do.
AUTO_ROUTING: dict[str, str] = {
    "extract_facts": "openai",  # extraction -> cheapest suitable model
    "research_background": "gemini",  # context writing -> cheap, solid prose
    "analyze": "anthropic",  # analysis -> strongest available reasoning
    "write_draft": "anthropic",  # final writing -> preferred writing model
    "fact_check": "openai",  # verification -> cheap, suitable for a compare-and-flag task
}

MAX_TOKENS_PER_STEP = 400

#: How often _run_step re-checks whether the job is still RUNNING while a
#: step is actually in flight (Phase 10). Cheap enough to poll frequently:
#: it only runs for the duration of one step, not the whole job.
CANCELLATION_POLL_SECONDS = 0.5

#: Search results are reused for an hour before a re-run treats them as
#: stale -- long enough that switching models mid-project doesn't trigger a
#: pointless re-search, short enough that "today's news" stays honest.
SOURCE_TTL_SECONDS = 3600

SEARCH_SOURCES_QUERY_SUFFIX = " latest news"
EXTRACT_FACTS_SYSTEM = (
    "You are a careful research assistant. Given a research task and a set "
    "of real, current search results, list the key facts and claims most "
    "relevant to the task as a short bulleted list, grounded in those "
    "sources rather than general knowledge alone."
)
RESEARCH_BACKGROUND_SYSTEM = (
    "You are a research assistant. Given a research task and a set of known "
    "facts, write a concise background paragraph (3-5 sentences) giving "
    "context for the topic."
)
ANALYZE_SYSTEM = (
    "You are an analyst. Given a research task and background context, "
    "write a short analysis (3-5 sentences) of what the topic means or why "
    "it matters."
)
WRITE_DRAFT_SYSTEM = (
    "You are a writer. Given a research task, background and analysis, "
    "write one concise draft paragraph suitable for a research summary."
)
FACT_CHECK_SYSTEM = (
    "You are a fact-checker. Given a draft and a list of known facts, note "
    "any inconsistencies or unsupported claims in 1-2 sentences, or confirm "
    "the draft is consistent with the facts."
)

#: V0.3 conversation history: the short AI-generated conversation title
#: (create_job's plain-truncated-text fallback is what shows until this
#: replaces it -- see _maybe_title_project).
TITLE_SYSTEM = (
    "Summarize the user's request in 2-4 words as a short conversation "
    "title. No punctuation, no quotes, no trailing period. Reply with "
    "just the title."
)
TITLE_MAX_TOKENS = 12
#: Upper bound on how long run_research_pipeline's `finally` will wait for
#: a still-in-flight title-gen call before giving up on it -- see the
#: finally block below for why this must never be unbounded.
TITLE_TASK_TIMEOUT_SECONDS = 5.0


async def _provision_internal_key(
    session_factory: async_sessionmaker[AsyncSession],
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """A fresh, single-job API key -- consistent with how every other API
    key in this system works (plaintext known only at creation; see
    app.provision's identical reasoning for invite keys). Deactivated in
    `run_research_pipeline`'s `finally` block once the job is done, so it
    can't be reused even if it somehow leaked.
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


async def _deactivate_key(
    session_factory: async_sessionmaker[AsyncSession], api_key_id: uuid.UUID
) -> None:
    async with session_factory() as session:
        api_key = await session.get(ApiKey, api_key_id)
        if api_key is not None:
            api_key.active = False
            await session.commit()


async def _project_slug(
    session_factory: async_sessionmaker[AsyncSession], project_id: uuid.UUID
) -> str:
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        return project.slug


async def _set_run_id(
    session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID, run_id: str
) -> None:
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        job.run_id = uuid.UUID(run_id)
        await session.commit()


async def _watch_for_cancellation(
    session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID
) -> None:
    """Polls until the job is no longer RUNNING. Raced against an in-flight
    step in _run_step (Phase 10) so a Cancel click actually interrupts a
    slow/hung provider call instead of waiting for it to finish or time out
    on its own -- before this, `job_control.guard()`'s pre-step check meant
    cancellation only took effect at the *next* step boundary, so a single
    stuck provider call could make Cancel silently do nothing for as long as
    that call kept running.
    """
    while await job_control.is_still_running(session_factory, job_id):
        await asyncio.sleep(CANCELLATION_POLL_SECONDS)


async def _run_step(
    cl: ComputeLayer,
    session_factory: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
    *,
    name: str,
    inputs: dict,
    fn: Callable[[], Awaitable[Any]],
    artifact_type: str | None,
    model: str | None = None,
    ttl: int | None = None,
    cross_model_reuse: bool = True,
) -> ComputeResult:
    await job_control.guard(session_factory, job_id)
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
    watch_task = asyncio.create_task(_watch_for_cancellation(session_factory, job_id))
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
    await job_control.emit(
        session_factory, job_id, "STEP_FINISHED", {"step": name, "cost_usd": result.cost_usd}
    )
    return result


def _resolve_provider(model_preference: str | None) -> tuple[Callable[..., Awaitable[str]], str]:
    module = PROVIDER_MODULES.get(model_preference or "", PROVIDER_MODULES[DEFAULT_PROVIDER])
    return module.complete, module.MODEL


def _resolve_step_provider(
    model_preference: str | None, step_name: str
) -> tuple[Callable[..., Awaitable[str]], str]:
    """Auto mode looks the step up in AUTO_ROUTING; every other preference
    (or an unrecognized one, via _resolve_provider's own fallback) uses the
    same provider for every step, exactly as before Phase 9.
    """
    if model_preference == AUTO_PREFERENCE:
        return _resolve_provider(AUTO_ROUTING[step_name])
    return _resolve_provider(model_preference)


def _llm_step(
    complete_fn: Callable[..., Awaitable[str]], system: str, prompt: str
) -> Callable[[], Awaitable[str]]:
    return lambda: complete_fn(system=system, prompt=prompt, max_tokens=MAX_TOKENS_PER_STEP)


async def _maybe_title_project(
    session_factory: async_sessionmaker[AsyncSession], job: Job
) -> None:
    """V0.3 conversation history: the first job in a project gets an
    AI-generated title, replacing create_job's plain-truncated-text
    fallback. Launched as a fire-and-forget asyncio.create_task from
    run_research_pipeline -- doesn't gate the main pipeline's progress,
    and only ever runs once per project (the cheap COUNT check below).

    Deliberately NOT wrapped in cl.compute.run(): a title has no future
    reuse value (each project's first message is unique by definition),
    so there's nothing the reuse engine would ever do with it -- it's a
    plain, uninstrumented call, with its own small cost added to
    job.spent_usd directly for honest accounting.
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


async def run_research_pipeline(
    job: Job,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    transport_factory: Callable[[str, str], Any] | None = None,
) -> None:
    """``transport_factory(api_key, project_slug) -> Transport`` is a test-only
    seam: when given, it builds the SDK transport instead of the normal
    api_key+base_url path (see ComputeLayer's own `transport=` override).
    Production never passes it -- tests use it to bind the SDK straight to
    an in-process ASGI transport (no real socket, no server lifecycle to
    race against) rather than a real HTTP server, since the *freshly minted*
    internal API key isn't known until after this function starts, so the
    transport can't be pre-built by the caller.
    """
    settings = get_settings()
    project_slug = await _project_slug(session_factory, job.project_id)
    api_key, api_key_id = await _provision_internal_key(
        session_factory, job.workspace_id, job.project_id
    )
    transport = transport_factory(api_key, project_slug) if transport_factory else None

    await job_control.emit(session_factory, job.id, "STARTED")
    # Fire-and-forget: runs concurrently with the steps below, doesn't
    # gate them. Held in a variable (not just `asyncio.create_task(...)`
    # on its own) so it can't be garbage-collected mid-flight -- a real
    # asyncio gotcha -- and awaited in `finally` so the worker doesn't move
    # on to the next job while this is still writing to the DB.
    title_task = asyncio.create_task(_maybe_title_project(session_factory, job))

    try:
        async with ComputeLayer(
            api_key=api_key,
            project=project_slug,
            base_url=settings.internal_api_url,
            transport=transport,
        ) as cl:
            async with cl.run(external_run_id=str(job.id)) as run:
                await _set_run_id(session_factory, job.id, run.id)
                task = job.task_text

                sources = await _run_step(
                    cl,
                    session_factory,
                    job.id,
                    name="search_sources",
                    inputs={"query": task},
                    fn=lambda: tavily.search(task + SEARCH_SOURCES_QUERY_SUFFIX),
                    artifact_type="source",
                    ttl=SOURCE_TTL_SECONDS,
                )
                sources_text = "\n".join(
                    f"- {item['title']}: {item['content']}" for item in sources.value
                ) or "(no search results found)"

                extract_facts_provider, extract_facts_model = _resolve_step_provider(
                    job.model_preference, "extract_facts"
                )
                facts = await _run_step(
                    cl,
                    session_factory,
                    job.id,
                    name="extract_facts",
                    inputs={"task": task, "sources": sources},
                    fn=_llm_step(
                        extract_facts_provider,
                        EXTRACT_FACTS_SYSTEM,
                        f"Task: {task}\n\nSearch results:\n{sources_text}",
                    ),
                    artifact_type="fact",
                    model=extract_facts_model,
                )

                research_provider, research_model = _resolve_step_provider(
                    job.model_preference, "research_background"
                )
                research = await _run_step(
                    cl,
                    session_factory,
                    job.id,
                    name="research_background",
                    inputs={"task": task, "facts": facts},
                    fn=_llm_step(
                        research_provider,
                        RESEARCH_BACKGROUND_SYSTEM,
                        f"Task: {task}\n\nKnown facts:\n{facts.value}",
                    ),
                    artifact_type="research_note",
                    model=research_model,
                )

                analyze_provider, analyze_model = _resolve_step_provider(
                    job.model_preference, "analyze"
                )
                analysis = await _run_step(
                    cl,
                    session_factory,
                    job.id,
                    name="analyze",
                    inputs={"task": task, "research": research},
                    fn=_llm_step(
                        analyze_provider, ANALYZE_SYSTEM, f"Task: {task}\n\nBackground:\n{research.value}"
                    ),
                    artifact_type="analysis",
                    model=analyze_model,
                )

                # write_draft and fact_check deliberately do NOT set
                # cross_model_reuse: per the spec's own model-switch example
                # ("Claude only needs to: Review relevant existing context,
                # Perform the requested rewrite"), only the *research*
                # (sources/facts/background/analysis) is meant to survive a
                # model switch untouched -- the draft is specifically what
                # the new model is being asked to (re)write, and a stale
                # fact-check against a *new* draft would be meaningless.
                # Reusing them here would make switching models free but
                # pointless: identical prose re-labeled under a model that
                # never actually wrote it.
                write_draft_provider, write_draft_model = _resolve_step_provider(
                    job.model_preference, "write_draft"
                )
                draft = await _run_step(
                    cl,
                    session_factory,
                    job.id,
                    name="write_draft",
                    inputs={"task": task, "analysis": analysis},
                    fn=_llm_step(
                        write_draft_provider,
                        WRITE_DRAFT_SYSTEM,
                        f"Task: {task}\n\nAnalysis:\n{analysis.value}",
                    ),
                    artifact_type="draft",
                    model=write_draft_model,
                    cross_model_reuse=False,
                )

                fact_check_provider, fact_check_model = _resolve_step_provider(
                    job.model_preference, "fact_check"
                )
                await _run_step(
                    cl,
                    session_factory,
                    job.id,
                    name="fact_check",
                    inputs={"draft": draft, "facts": facts},
                    fn=_llm_step(
                        fact_check_provider,
                        FACT_CHECK_SYSTEM,
                        f"Draft:\n{draft.value}\n\nKnown facts:\n{facts.value}",
                    ),
                    artifact_type=None,
                    model=fact_check_model,
                    cross_model_reuse=False,
                )

        async with session_factory() as session:
            live_job = await session.get(Job, job.id)
            if live_job.status != "RUNNING":
                return  # cancelled during the last step
            live_job.status = "SUCCEEDED"
            live_job.current_step = None
            # The clean assistant-facing reply (V0.3 chat turn): write_draft's
            # output, not fact_check's -- fact_check is a QA side-step whose
            # own output is a verification note, never the shown answer.
            live_job.answer_text = draft.value
            live_job.finished_at = utcnow()
            await session.commit()
        await job_control.emit(session_factory, job.id, "SUCCEEDED")

    except JobCancelled:
        return  # status already CANCELLED, set externally -- nothing to do

    except CostCapReached:
        async with session_factory() as session:
            live_job = await session.get(Job, job.id)
            if live_job.status == "RUNNING":
                live_job.status = "FAILED"
                live_job.error_message = "cost cap reached"
                live_job.finished_at = utcnow()
                await session.commit()
        await job_control.emit(session_factory, job.id, "FAILED", {"reason": "cost_cap"})

    finally:
        await _deactivate_key(session_factory, api_key_id)
        # Bounded, not an unconditional await: title_task shares whichever
        # provider the job used, so an unusually slow (or, worst case,
        # hung) real call there must never stall the *job's* own
        # completion/cancellation -- asyncio.wait_for cancels it on
        # timeout. In the ordinary case this never fires: one quick
        # title-gen call finishes well before the full multi-step pipeline
        # does, title_task is already done by the time we get here.
        with contextlib.suppress(BaseException):
            await asyncio.wait_for(title_task, timeout=TITLE_TASK_TIMEOUT_SECONDS)
