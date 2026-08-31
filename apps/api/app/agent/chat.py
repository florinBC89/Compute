"""One streamed chat turn (V0.3 chat component): the default execution path
for every message, replacing the six-step research pipeline
(app.agent.pipeline) in the live flow. The pipeline itself is untouched and
undeployed -- kept in the repo for a possible future explicit research mode
(see docker-compose.yml's now-commented-out `worker` service, which is what
used to run it).

The core mechanism: `cl.compute.run(fn=...)` requires `fn()` to resolve to
ONE materialized value, but `fn()` can internally stream to an
`asyncio.Queue` side-channel (`delta_queue`) while it accumulates that
value. On a cache MISS, `_stream_and_record` calls the provider's streaming
API, pushes each chunk onto `delta_queue` as it arrives, accumulates the
full text, and returns it once the call finishes -- its own `finally` then
pushes the `None` sentinel that tells the route consumer no more deltas are
coming *from that call*. On a cache HIT, `fn` is never called at all --
nothing from it is ever pushed onto `delta_queue` -- and `compute.run()`
returns the cached result almost instantly; in that case it's this module's
own unconditional `finally` (see `run_chat_turn` below) that pushes the
`None` sentinel instead, since `_stream_and_record` never ran. Either way
the consumer (app.routes.jobs's new `/stream` route) is guaranteed exactly
one `None` to key off, racing the turn task against the next queue item the
same way app.agent.pipeline._run_step already races a step against
cancellation.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, Callable

from computelayer import ComputeLayer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent import job_control, turn_common
from app.agent.job_control import CostCapReached, JobCancelled
from app.config import get_settings
from app.models import Job
from app.models.base import utcnow
from app.services import jobs as jobs_service

__all__ = ["run_chat_turn"]

CHAT_SYSTEM = (
    "You are a helpful, direct conversational assistant. Answer the user's "
    "latest message clearly and concisely, using the prior turns of this "
    "conversation for context where relevant. Don't restate context you "
    "were just given, and don't pad your answer with unnecessary caveats "
    "or filler."
)
CHAT_MAX_TOKENS = 1024

#: Mirrors app.agent.pipeline.TITLE_TASK_TIMEOUT_SECONDS exactly (see that
#: module's own `finally` block for why this bound exists: title_task
#: shares whichever provider the job used, so an unusually slow call there
#: must never stall the turn's own completion/cancellation).
TITLE_TASK_TIMEOUT_SECONDS = 5.0


def _resolve_provider_module(model_preference: str | None) -> Any:
    """Same fallback as turn_common.resolve_provider (job.model_preference,
    or DEFAULT_PROVIDER if unset/unrecognized), but hands back the provider
    *module* itself rather than a captured `.complete` reference --
    resolve_provider was built for pipeline.py's non-streaming per-step
    `.complete()` calls, and doesn't expose `.stream_complete`, which is
    what a chat turn actually needs.

    Looking the module up fresh here (rather than capturing
    `.stream_complete` itself) keeps this monkeypatch-friendly for exactly
    the reason turn_common.PROVIDER_MODULES's own docstring gives: a test's
    `monkeypatch.setattr(provider_module, "stream_complete", ...)` changes
    the module's attribute, and `provider_module.stream_complete(...)`
    below still resolves that attribute fresh at call time.
    """
    return turn_common.PROVIDER_MODULES.get(
        model_preference or "", turn_common.PROVIDER_MODULES[turn_common.DEFAULT_PROVIDER]
    )


async def _load_history(
    session_factory: async_sessionmaker[AsyncSession], job: Job
) -> list[dict[str, str]]:
    async with session_factory() as session:
        return await jobs_service.build_chat_history(
            session, job.project_id, before_job_id=job.id
        )


async def run_chat_turn(
    job: Job,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    delta_queue: asyncio.Queue,
    transport_factory: Callable[[str, str], Any] | None = None,
) -> None:
    """Runs exactly one streamed `cl.compute.run()` call for `job` and
    writes its progress to `delta_queue` as it happens.

    `delta_queue` items are dicts -- `{"type": "delta", "text": ...}` for
    each streamed chunk, `{"type": "title", "name": ...}` if this is the
    project's first turn and title generation finishes in time -- or the
    sentinel `None`, which is always eventually pushed exactly once from
    wherever the turn's last chance to push it is (see the module
    docstring for how a cache HIT vs MISS each reach that point).

    `transport_factory` is the same test-only seam
    app.agent.pipeline.run_research_pipeline already takes: when given, it
    builds the SDK transport instead of the normal api_key+base_url path,
    binding straight to an in-process ASGI transport rather than a real
    socket. Production never passes it.

    Never raises: every failure mode is caught and turned into a FAILED job
    (mirroring app.agent.pipeline.run_research_pipeline's own exception
    handling), so app.routes.jobs's `/stream` route never needs special-case
    error handling around this call.
    """
    settings = get_settings()
    project_slug = await turn_common.project_slug(session_factory, job.project_id)
    api_key, api_key_id = await turn_common.provision_internal_key(
        session_factory, job.workspace_id, job.project_id
    )
    transport = transport_factory(api_key, project_slug) if transport_factory else None

    # Fire-and-forget, same as pipeline.py: runs concurrently with the turn
    # below, doesn't gate it. Held in a variable so it can't be
    # garbage-collected mid-flight, awaited (bounded) in `finally` so this
    # function doesn't return while it's still writing to the DB.
    title_task = asyncio.create_task(
        turn_common.maybe_title_project(
            session_factory,
            job,
            on_titled=lambda name: delta_queue.put({"type": "title", "name": name}),
        )
    )

    try:
        async with ComputeLayer(
            api_key=api_key,
            project=project_slug,
            base_url=settings.internal_api_url,
            transport=transport,
        ) as cl:
            async with cl.run(external_run_id=str(job.id)) as run:
                await turn_common.set_run_id(session_factory, job.id, run.id)
                history = await _load_history(session_factory, job)
                provider_module = _resolve_provider_module(job.model_preference)
                model = provider_module.MODEL

                async def _stream_and_record() -> str:
                    try:
                        return await provider_module.stream_complete(
                            system=CHAT_SYSTEM,
                            history=history,
                            message=job.task_text,
                            max_tokens=CHAT_MAX_TOKENS,
                            on_delta=lambda text: delta_queue.put(
                                {"type": "delta", "text": text}
                            ),
                        )
                    finally:
                        # Tells the route consumer no more deltas are coming
                        # from *this* call -- only reached on a cache MISS,
                        # since fn() (this closure) is never invoked at all
                        # on a HIT. See the module docstring.
                        await delta_queue.put(None)

                result = await turn_common.run_computation(
                    cl,
                    session_factory,
                    job.id,
                    name="chat_turn",
                    inputs={"history": history, "message": job.task_text},
                    fn=_stream_and_record,
                    model=model,
                    artifact_type=None,
                    ttl=None,
                    cross_model_reuse=False,
                    emit_events=False,
                )
                # NOTE: turn_common.run_computation already calls
                # job_control.add_spend for any nonzero result.cost_usd --
                # that add_spend call is unconditional there, not gated on
                # emit_events=False (only the STEP_STARTED/STEP_FINISHED
                # JobEvents are). Calling add_spend again here would
                # double-count this turn's spend against job.spent_usd and
                # the cost cap, so this deliberately does NOT repeat it.

        async with session_factory() as session:
            live_job = await session.get(Job, job.id)
            if live_job.status != "RUNNING":
                return  # cancelled during the call -- status already set externally
            live_job.status = "SUCCEEDED"
            live_job.answer_text = result.value
            live_job.finished_at = utcnow()
            await session.commit()

    except JobCancelled:
        return  # status already CANCELLED, set externally -- nothing to do

    except CostCapReached:
        await turn_common.mark_failed(session_factory, job.id, "cost cap reached")
        await job_control.emit(session_factory, job.id, "FAILED", {"reason": "cost_cap"})

    except Exception:
        await turn_common.mark_failed(session_factory, job.id, "internal error")
        await job_control.emit(session_factory, job.id, "FAILED", {"reason": "internal_error"})

    finally:
        # Redundant safety-net sentinel: covers every path that could reach
        # here without _stream_and_record's own `finally` ever having run
        # (e.g. provision_internal_key itself raising, or a cache HIT where
        # fn() was never called) -- guarantees the consumer always sees a
        # None eventually, no matter how this turn ended.
        await delta_queue.put(None)
        await turn_common.deactivate_key(session_factory, api_key_id)
        with contextlib.suppress(BaseException):
            await asyncio.wait_for(title_task, timeout=TITLE_TASK_TIMEOUT_SECONDS)
