"""Jobs API + real research pipeline (V0.2 human-workspace slice).

Covers job creation (incl. default-project auto-provisioning), ownership
checks, cancellation, the SSE events endpoint closing once a terminal event
has been sent, and the real pipeline (search_sources -> extract_facts ->
research_background -> analyze -> write_draft -> fact_check) running a job
to completion, respecting an externally-set CANCELLED status mid-pipeline,
and stopping on a cost-cap breach -- with the LLM/search calls mocked (see
`fake_openai`/`fake_tavily`) so this suite runs free and deterministically.
"""

from __future__ import annotations

import os
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
