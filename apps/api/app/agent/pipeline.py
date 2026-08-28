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
Everything downstream is OpenAI-only for now (Phase 7 adds Anthropic/Gemini
behind the same `openai_provider.complete` shape).
"""

from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable

from computelayer import ComputeLayer
from computelayer.result import ComputeResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent import job_control, tavily
from app.agent.job_control import CostCapReached, JobCancelled
from app.agent.providers import openai as openai_provider
from app.config import get_settings
from app.models import ApiKey, Job, Project
from app.models.base import utcnow
from app.services.scope import KEY_PREFIX_LENGTH, generate_api_key, hash_api_key

__all__ = ["run_research_pipeline", "CostCapReached", "JobCancelled"]

MODEL = openai_provider.MODEL
MAX_TOKENS_PER_STEP = 400

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
) -> ComputeResult:
    await job_control.guard(session_factory, job_id)
    await job_control.set_current_step(session_factory, job_id, name)
    await job_control.emit(session_factory, job_id, "STEP_STARTED", {"step": name})

    result = await cl.compute.run(
        name=name,
        inputs=inputs,
        fn=fn,
        model=model,
        artifact_type=artifact_type,
        cross_model_reuse=True,
        ttl=ttl,
    )

    if result.cost_usd:
        await job_control.add_spend(session_factory, job_id, result.cost_usd)
    await job_control.emit(
        session_factory, job_id, "STEP_FINISHED", {"step": name, "cost_usd": result.cost_usd}
    )
    return result


def _llm_step(system: str, prompt: str) -> Callable[[], Awaitable[str]]:
    return lambda: openai_provider.complete(
        system=system, prompt=prompt, max_tokens=MAX_TOKENS_PER_STEP
    )


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

                facts = await _run_step(
                    cl,
                    session_factory,
                    job.id,
                    name="extract_facts",
                    inputs={"task": task, "sources": sources},
                    fn=_llm_step(
                        EXTRACT_FACTS_SYSTEM, f"Task: {task}\n\nSearch results:\n{sources_text}"
                    ),
                    artifact_type="fact",
                    model=MODEL,
                )

                research = await _run_step(
                    cl,
                    session_factory,
                    job.id,
                    name="research_background",
                    inputs={"task": task, "facts": facts},
                    fn=_llm_step(
                        RESEARCH_BACKGROUND_SYSTEM,
                        f"Task: {task}\n\nKnown facts:\n{facts.value}",
                    ),
                    artifact_type="research_note",
                    model=MODEL,
                )

                analysis = await _run_step(
                    cl,
                    session_factory,
                    job.id,
                    name="analyze",
                    inputs={"task": task, "research": research},
                    fn=_llm_step(
                        ANALYZE_SYSTEM, f"Task: {task}\n\nBackground:\n{research.value}"
                    ),
                    artifact_type="analysis",
                    model=MODEL,
                )

                draft = await _run_step(
                    cl,
                    session_factory,
                    job.id,
                    name="write_draft",
                    inputs={"task": task, "analysis": analysis},
                    fn=_llm_step(
                        WRITE_DRAFT_SYSTEM, f"Task: {task}\n\nAnalysis:\n{analysis.value}"
                    ),
                    artifact_type="draft",
                    model=MODEL,
                )

                await _run_step(
                    cl,
                    session_factory,
                    job.id,
                    name="fact_check",
                    inputs={"draft": draft, "facts": facts},
                    fn=_llm_step(
                        FACT_CHECK_SYSTEM, f"Draft:\n{draft.value}\n\nKnown facts:\n{facts.value}"
                    ),
                    artifact_type=None,
                    model=MODEL,
                )

        async with session_factory() as session:
            live_job = await session.get(Job, job.id)
            if live_job.status != "RUNNING":
                return  # cancelled during the last step
            live_job.status = "SUCCEEDED"
            live_job.current_step = None
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
