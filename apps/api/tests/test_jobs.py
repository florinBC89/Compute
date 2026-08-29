"""Jobs API + real research pipeline (V0.2 human-workspace slice).

Covers job creation (incl. default-project auto-provisioning), ownership
checks, cancellation (both between pipeline steps and mid-provider-call,
Phase 10), the SSE events endpoint closing once a terminal event has been
sent, and the real pipeline (search_sources -> extract_facts ->
research_background -> analyze -> write_draft -> fact_check) running a job
to completion, respecting an externally-set CANCELLED status mid-pipeline,
and stopping on a cost-cap breach -- with the LLM/search calls mocked (see
`fake_openai`/`fake_anthropic`/`fake_gemini`/`fake_tavily`) so this suite
runs free and deterministically. Also covers manual per-run provider
selection (Phase 7) and static per-step Auto-mode routing (Phase 9).
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

SUPABASE_URL = "https://test-project.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
KID = "test-signing-key"


@pytest.fixture(scope="module")
def keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()


def _make_token(keypair, *, sub: str, email: str) -> str:
    private_key, _ = keypair
    payload = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "iss": ISSUER,
        "exp": 9_999_999_999,
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": KID})


@pytest_asyncio.fixture
async def workspace_http_client(engine, keypair, monkeypatch):
    os.environ["SUPABASE_URL"] = SUPABASE_URL
    from app.config import get_settings

    get_settings.cache_clear()

    _, public_key = keypair

    class _FakeSigningKey:
        def __init__(self, key):
            self.key = key

    class _FakeJWKClient:
        def get_signing_key_from_jwt(self, token: str):
            return _FakeSigningKey(public_key)

    import app.services.supabase_auth as supabase_auth

    monkeypatch.setattr(
        supabase_auth, "_jwks_client", lambda supabase_url: _FakeJWKClient()
    )

    import app.db as db

    db._engine = engine
    db._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    from app.main import app as fastapi_app

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://testserver/v1"
    ) as client:
        yield client

    await db.dispose_engine()


@pytest_asyncio.fixture
async def auth_headers(workspace_http_client, keypair):
    token = _make_token(keypair, sub=str(uuid.uuid4()), email="researcher@example.com")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_job_auto_provisions_default_project(
    workspace_http_client, auth_headers
):
    response = await workspace_http_client.post(
        "/jobs", json={"task_text": "research today's AI news"}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["task_text"] == "research today's AI news"
    assert body["spent_usd"] == 0.0
    assert body["cost_cap_usd"] == 0.50
    assert uuid.UUID(body["id"])

    me = await workspace_http_client.get("/me", headers=auth_headers)
    assert [p["slug"] for p in me.json()["projects"]] == ["default"]


@pytest.mark.asyncio
async def test_empty_task_text_is_rejected(workspace_http_client, auth_headers):
    response = await workspace_http_client.post(
        "/jobs", json={"task_text": "   "}, headers=auth_headers
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_job_requires_ownership(workspace_http_client, keypair):
    owner_token = _make_token(keypair, sub=str(uuid.uuid4()), email="owner@example.com")
    other_token = _make_token(keypair, sub=str(uuid.uuid4()), email="other@example.com")

    created = await workspace_http_client.post(
        "/jobs",
        json={"task_text": "owner's task"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    job_id = created.json()["id"]

    as_owner = await workspace_http_client.get(
        f"/jobs/{job_id}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    as_other = await workspace_http_client.get(
        f"/jobs/{job_id}", headers={"Authorization": f"Bearer {other_token}"}
    )

    assert as_owner.status_code == 200
    assert as_other.status_code == 404


@pytest.mark.asyncio
async def test_cancel_queued_job(workspace_http_client, auth_headers):
    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "cancel me"}, headers=auth_headers
    )
    job_id = created.json()["id"]

    response = await workspace_http_client.post(
        f"/jobs/{job_id}/cancel", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


@pytest_asyncio.fixture
async def pipeline_transport_factory(workspace_http_client):
    """A `transport_factory` for `run_research_pipeline` (see its docstring)
    that binds the SDK straight to this test's ASGI app in-process -- no
    real socket, no server lifecycle. This tests the exact same request
    handling a real HTTP server would (same FastAPI app, same routes, same
    dependency-scoped session), just without a TCP round-trip.

    An earlier version of this fixture spun up a real uvicorn server per
    test; that introduced a genuine cross-test race (one test's late
    in-flight request occasionally landing on the next test's freshly
    recreated schema) for no benefit this in-process approach doesn't also
    give -- kept as a lesson, not as code.
    """
    from computelayer.transport import HttpTransport
    from httpx import ASGITransport as _ASGITransport
    from httpx import AsyncClient as _AsyncClient

    from app.main import app as fastapi_app

    clients: list[Any] = []

    def factory(api_key: str, project_slug: str):
        client = _AsyncClient(
            transport=_ASGITransport(app=fastapi_app),
            base_url="http://testserver/v1",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        clients.append(client)
        return HttpTransport(
            api_key=api_key, base_url="http://testserver/v1", project=project_slug, client=client
        )

    yield factory

    for client in clients:
        await client.aclose()


@pytest_asyncio.fixture
async def fake_openai(monkeypatch):
    """Replaces the real OpenAI call with a fast, free, deterministic one --
    it still calls record_llm_call() with the same shape the real provider
    module does, so Compute.run()'s cost ledger works exactly as it would
    for a real call. `calls` lets a test control/observe per-call cost.
    """
    from app.agent.providers import openai as openai_provider
    from computelayer.context import LLMCall, record_llm_call

    calls: list[float] = []  # cost_usd per call, in order; default 0.001 each

    async def _fake_complete(*, system: str, prompt: str, max_tokens: int = 400) -> str:
        cost = calls.pop(0) if calls else 0.001
        record_llm_call(
            LLMCall(
                model=openai_provider.MODEL,
                provider="openai",
                input_tokens=50,
                output_tokens=50,
                cost_usd=cost,
                latency_ms=5,
            )
        )
        return f"[fake completion for: {prompt[:40]}]"

    monkeypatch.setattr(openai_provider, "complete", _fake_complete)
    return calls


@pytest_asyncio.fixture
async def fake_anthropic(monkeypatch):
    """Same shape as fake_openai, for the anthropic provider module --
    lets a test prove model_preference="anthropic" actually dispatches
    there instead of silently falling through to OpenAI.
    """
    from app.agent.providers import anthropic as anthropic_provider
    from computelayer.context import LLMCall, record_llm_call

    calls: list[float] = []

    async def _fake_complete(*, system: str, prompt: str, max_tokens: int = 400) -> str:
        cost = calls.pop(0) if calls else 0.001
        record_llm_call(
            LLMCall(
                model=anthropic_provider.MODEL,
                provider="anthropic",
                input_tokens=50,
                output_tokens=50,
                cost_usd=cost,
                latency_ms=5,
            )
        )
        return f"[fake claude completion for: {prompt[:40]}]"

    monkeypatch.setattr(anthropic_provider, "complete", _fake_complete)
    return calls


@pytest_asyncio.fixture
async def fake_gemini(monkeypatch):
    """Same shape as fake_openai/fake_anthropic, for the gemini provider
    module -- needed by the Auto-mode routing test (Phase 9), the first
    test to exercise all three providers in a single pipeline run.
    """
    from app.agent.providers import gemini as gemini_provider
    from computelayer.context import LLMCall, record_llm_call

    calls: list[float] = []

    async def _fake_complete(*, system: str, prompt: str, max_tokens: int = 400) -> str:
        cost = calls.pop(0) if calls else 0.001
        record_llm_call(
            LLMCall(
                model=gemini_provider.MODEL,
                provider="gemini",
                input_tokens=50,
                output_tokens=50,
                cost_usd=cost,
                latency_ms=5,
            )
        )
        return f"[fake gemini completion for: {prompt[:40]}]"

    monkeypatch.setattr(gemini_provider, "complete", _fake_complete)
    return calls


@pytest_asyncio.fixture
async def fake_tavily(monkeypatch):
    """Replaces the real Tavily call -- no automated test should make a
    real, billed call to a third-party search API.
    """
    from app.agent import tavily

    async def _fake_search(query: str, *, max_results: int = 5) -> list[dict[str, str]]:
        return [
            {"title": "Fake Source", "url": "https://example.com", "content": f"About: {query}"}
        ]

    monkeypatch.setattr(tavily, "search", _fake_search)


@pytest.mark.asyncio
async def test_pipeline_runs_to_completion(
    workspace_http_client,
    auth_headers,
    engine,
    pipeline_transport_factory,
    fake_openai,
    fake_tavily,
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import worker
    from app.models import Computation, Job, JobEvent, Run

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "research today's AI infrastructure news"},
        headers=auth_headers,
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    claimed = await worker._claim_next_job(session_factory)
    assert claimed is not None and claimed.id == job_id

    await worker._run_one(
        session_factory, claimed, transport_factory=pipeline_transport_factory
    )

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "SUCCEEDED"
        assert job.current_step is None
        assert job.finished_at is not None
        assert job.run_id is not None
        assert 0 < float(job.spent_usd) < float(job.cost_cap_usd)
        # V0.3 Phase 0: the clean assistant-facing answer is write_draft's
        # output, not fact_check's (a QA side-step, never the shown answer).
        assert job.answer_text is not None
        assert job.answer_text.startswith("[fake completion for:")

        run = await session.get(Run, job.run_id)
        assert run is not None and run.status == "SUCCEEDED"

        computations = (
            await session.execute(
                Computation.__table__.select().where(Computation.run_id == job.run_id)
            )
        ).mappings().all()
        assert {c["name"] for c in computations} == {
            "search_sources",
            "extract_facts",
            "research_background",
            "analyze",
            "write_draft",
            "fact_check",
        }
        artifact_types = {c["name"]: c["artifact_type"] for c in computations}
        assert artifact_types["search_sources"] == "source"
        assert artifact_types["extract_facts"] == "fact"
        assert artifact_types["fact_check"] is None

        events = (
            (
                await session.execute(
                    JobEvent.__table__.select()
                    .where(JobEvent.job_id == job_id)
                    .order_by(JobEvent.id)
                )
            )
            .mappings()
            .all()
        )
        event_types = [e["event_type"] for e in events]
        assert event_types == (
            ["QUEUED", "STARTED"]
            + ["STEP_STARTED", "STEP_FINISHED"] * 6
            + ["SUCCEEDED"]
        )


@pytest.mark.asyncio
async def test_pipeline_stops_when_job_is_cancelled_mid_pipeline(
    workspace_http_client,
    auth_headers,
    engine,
    pipeline_transport_factory,
    fake_openai,
    fake_tavily,
    monkeypatch,
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import worker
    from app.agent import job_control
    from app.models import Job

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "cancel mid-flight"}, headers=auth_headers
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    claimed = await worker._claim_next_job(session_factory)

    original_emit = job_control.emit
    call_count = 0

    async def _emit_then_cancel(session_factory, job_id_arg, event_type, payload=None):
        nonlocal call_count
        call_count += 1
        await original_emit(session_factory, job_id_arg, event_type, payload)
        if event_type == "STEP_FINISHED" and call_count >= 4:  # after search_sources + extract_facts
            async with session_factory() as session:
                job = await session.get(Job, job_id_arg)
                job.status = "CANCELLED"
                await session.commit()

    # pipeline.py calls `job_control.emit(...)` as an attribute lookup on
    # the module object each time, so patching it here (the same module
    # object pipeline.py imported) is enough -- no separate patch needed.
    monkeypatch.setattr(job_control, "emit", _emit_then_cancel)

    await worker._run_one(
        session_factory, claimed, transport_factory=pipeline_transport_factory
    )

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        # The pipeline must not clobber the externally-set CANCELLED status
        # back to SUCCEEDED.
        assert job.status == "CANCELLED"


@pytest.mark.asyncio
async def test_pipeline_stops_when_cost_cap_reached(
    workspace_http_client,
    auth_headers,
    engine,
    pipeline_transport_factory,
    fake_openai,
    fake_tavily,
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import worker
    from app.models import Computation, Job

    # search_sources (step 1) costs nothing; extract_facts (step 2, the
    # first OpenAI call) costs $0.05. The job's cap ($0.03, set below) is
    # exceeded after it, so the guard before step 3 must stop the pipeline
    # there.
    fake_openai.append(0.05)

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "expensive task"}, headers=auth_headers
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        job.cost_cap_usd = 0.03
        await session.commit()

    claimed = await worker._claim_next_job(session_factory)
    await worker._run_one(
        session_factory, claimed, transport_factory=pipeline_transport_factory
    )

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "FAILED"
        assert job.error_message == "cost cap reached"
        assert float(job.spent_usd) == pytest.approx(0.05)

        # The artifacts already produced stay -- and reusable -- even
        # though the job overall failed on cost.
        computations = (
            await session.execute(
                Computation.__table__.select().where(Computation.run_id == job.run_id)
            )
        ).mappings().all()
        assert {c["name"] for c in computations} == {"search_sources", "extract_facts"}
        assert all(c["status"] == "SUCCEEDED" and c["reusable"] for c in computations)


@pytest.mark.asyncio
async def test_events_stream_closes_after_terminal_event(
    workspace_http_client, auth_headers, engine
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models import Job, JobEvent

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "pre-finished job"}, headers=auth_headers
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        job.status = "SUCCEEDED"
        session.add(JobEvent(job_id=job_id, event_type="SUCCEEDED", payload={}))
        await session.commit()

    async with workspace_http_client.stream(
        "GET", f"/jobs/{job_id}/events", headers=auth_headers
    ) as response:
        assert response.status_code == 200
        lines = [line async for line in response.aiter_lines() if line]

    assert any('"event_type":"QUEUED"' in line for line in lines)
    assert any('"event_type":"SUCCEEDED"' in line for line in lines)


@pytest.mark.asyncio
async def test_pipeline_dispatches_to_the_requested_provider(
    workspace_http_client,
    auth_headers,
    engine,
    pipeline_transport_factory,
    fake_openai,
    fake_anthropic,
    fake_tavily,
):
    """model_preference="anthropic" must call the anthropic provider, not
    silently fall through to OpenAI -- a real bug once caught here (a
    module-level dict of captured `(complete_fn, MODEL)` tuples stopped
    following `monkeypatch.setattr`, which let a cost-cap test call the
    *real* OpenAI API because the fixture's patch had no effect on the
    already-captured reference).
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import worker
    from app.models import Computation, Job

    created = await workspace_http_client.post(
        "/jobs",
        json={"task_text": "switch to claude", "model_preference": "anthropic"},
        headers=auth_headers,
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    claimed = await worker._claim_next_job(session_factory)
    await worker._run_one(
        session_factory, claimed, transport_factory=pipeline_transport_factory
    )

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "SUCCEEDED"

        computations = (
            await session.execute(
                Computation.__table__.select().where(Computation.run_id == job.run_id)
            )
        ).mappings().all()
        models_used = {c["model"] for c in computations if c["model"] is not None}
        assert models_used == {"anthropic/claude-haiku-4-5"}


@pytest.mark.asyncio
async def test_pipeline_falls_back_to_default_provider_for_unrecognized_preference(
    workspace_http_client,
    auth_headers,
    engine,
    pipeline_transport_factory,
    fake_openai,
    fake_anthropic,
    fake_tavily,
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import worker
    from app.models import Computation, Job

    created = await workspace_http_client.post(
        "/jobs",
        json={"task_text": "typo'd model", "model_preference": "chatgpt-please"},
        headers=auth_headers,
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    claimed = await worker._claim_next_job(session_factory)
    await worker._run_one(
        session_factory, claimed, transport_factory=pipeline_transport_factory
    )

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "SUCCEEDED"

        computations = (
            await session.execute(
                Computation.__table__.select().where(Computation.run_id == job.run_id)
            )
        ).mappings().all()
        models_used = {c["model"] for c in computations if c["model"] is not None}
        assert models_used == {"openai/gpt-4o-mini"}


@pytest.mark.asyncio
async def test_auto_mode_routes_different_steps_to_different_providers(
    workspace_http_client,
    auth_headers,
    engine,
    pipeline_transport_factory,
    fake_openai,
    fake_anthropic,
    fake_gemini,
    fake_tavily,
):
    """model_preference="auto" (Phase 9) must route each LLM step through
    app.agent.pipeline.AUTO_ROUTING rather than picking one provider for the
    whole run -- the actual product promise: an Auto task visibly uses more
    than one model, matching per app.agent.pipeline.AUTO_ROUTING.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import worker
    from app.agent.pipeline import AUTO_ROUTING, PROVIDER_MODULES
    from app.models import Computation, Job

    created = await workspace_http_client.post(
        "/jobs",
        json={"task_text": "auto-routed task", "model_preference": "auto"},
        headers=auth_headers,
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    claimed = await worker._claim_next_job(session_factory)
    await worker._run_one(
        session_factory, claimed, transport_factory=pipeline_transport_factory
    )

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "SUCCEEDED"

        computations = (
            await session.execute(
                Computation.__table__.select().where(Computation.run_id == job.run_id)
            )
        ).mappings().all()
        model_by_step = {c["name"]: c["model"] for c in computations}

        for step_name, provider_key in AUTO_ROUTING.items():
            assert model_by_step[step_name] == PROVIDER_MODULES[provider_key].MODEL

        # Not every step landed on the same provider -- the actual point of
        # Auto mode, and what distinguishes it from the single-provider path
        # covered by test_pipeline_dispatches_to_the_requested_provider.
        assert len(set(AUTO_ROUTING.values())) > 1


@pytest.mark.asyncio
async def test_cancel_interrupts_a_hanging_provider_call(
    workspace_http_client,
    auth_headers,
    engine,
    pipeline_transport_factory,
    fake_tavily,
    monkeypatch,
):
    """Phase 10: before this, a Cancel click only took effect at the *next*
    step boundary (job_control.guard()'s pre-step check) -- a single stuck
    provider call could make Cancel do nothing until that call eventually
    finished or timed out on its own. Proves the fix by hanging the
    extract_facts call for 60s and cancelling shortly after it starts: the
    job must reach CANCELLED in well under 60s, not after the hang.
    """
    from app.agent import pipeline as pipeline_module
    from app.agent.providers import openai as openai_provider
    from app import worker
    from app.models import Job

    # Fast poll so the test doesn't itself wait a real 0.5s per iteration.
    monkeypatch.setattr(pipeline_module, "CANCELLATION_POLL_SECONDS", 0.01)

    call_started = asyncio.Event()

    async def _hanging_complete(*, system: str, prompt: str, max_tokens: int = 400) -> str:
        call_started.set()
        await asyncio.sleep(60)
        return "should never be reached"

    monkeypatch.setattr(openai_provider, "complete", _hanging_complete)

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "cancel mid llm call"}, headers=auth_headers
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    claimed = await worker._claim_next_job(session_factory)

    async def _cancel_once_call_starts() -> None:
        await call_started.wait()
        async with session_factory() as session:
            job = await session.get(Job, job_id)
            job.status = "CANCELLED"
            await session.commit()

    canceller = asyncio.create_task(_cancel_once_call_starts())
    started = time.monotonic()
    await worker._run_one(session_factory, claimed, transport_factory=pipeline_transport_factory)
    elapsed = time.monotonic() - started
    await canceller

    # Generous versus the 60s hang, tight enough to prove it didn't wait it out.
    assert elapsed < 10

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "CANCELLED"


@pytest.mark.asyncio
async def test_per_workspace_cap_skips_a_saturated_workspace(
    workspace_http_client, auth_headers, engine
):
    """Phase 10: _claim_next_job's per-workspace cap is what stops one
    workspace queuing many jobs from starving every other workspace once
    the worker runs several jobs concurrently -- without it, a workspace's
    own backlog would simply claim every free concurrent slot.
    """
    from app import worker
    from app.models import Job

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    first = await workspace_http_client.post(
        "/jobs", json={"task_text": "job one"}, headers=auth_headers
    )
    second = await workspace_http_client.post(
        "/jobs", json={"task_text": "job two"}, headers=auth_headers
    )
    first_id = uuid.UUID(first.json()["id"])
    second_id = uuid.UUID(second.json()["id"])

    claimed_first = await worker._claim_next_job(session_factory, max_per_workspace=1)
    assert claimed_first is not None and claimed_first.id == first_id

    # The workspace already has one RUNNING job -- with a cap of 1, its
    # second QUEUED job must not be claimable yet, even though nothing else
    # is competing for the slot.
    assert await worker._claim_next_job(session_factory, max_per_workspace=1) is None

    async with session_factory() as session:
        job = await session.get(Job, first_id)
        job.status = "SUCCEEDED"
        await session.commit()

    # Finishing the first job frees the workspace's one slot.
    claimed_second = await worker._claim_next_job(session_factory, max_per_workspace=1)
    assert claimed_second is not None and claimed_second.id == second_id


@pytest.mark.asyncio
async def test_provider_outage_is_classified_separately_from_other_errors(
    workspace_http_client,
    auth_headers,
    engine,
    pipeline_transport_factory,
    monkeypatch,
):
    """A real provider/network failure should surface as error_message
    "provider unavailable" -- distinct from the generic "internal error"
    catch-all -- so apps/workspace can tell a user to try again shortly
    instead of implying a bug in the product itself.
    """
    import httpx as httpx_module

    from app import worker
    from app.agent import tavily
    from app.models import Job

    async def _broken_search(query: str, *, max_results: int = 5):
        raise httpx_module.ConnectError("connection refused")

    monkeypatch.setattr(tavily, "search", _broken_search)

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "provider is down"}, headers=auth_headers
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    claimed = await worker._claim_next_job(session_factory)
    await worker._run_one(session_factory, claimed, transport_factory=pipeline_transport_factory)

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "FAILED"
        assert job.error_message == "provider unavailable"
