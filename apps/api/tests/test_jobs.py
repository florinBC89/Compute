"""Jobs API + worker (V0.2 human-workspace slice, Phase 3).

Covers job creation (incl. default-project auto-provisioning), ownership
checks, cancellation, the worker's stub pipeline running a job to
completion, the worker respecting an externally-set CANCELLED status
mid-pipeline, and the SSE events endpoint closing once a terminal event has
been sent.
"""

from __future__ import annotations

import os
import uuid

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


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture
async def internal_api_url(workspace_http_client):
    """A *real* uvicorn server bound to a local port, sharing this test
    process's already-test-wired db._engine/_sessionmaker. app.agent.pipeline
    makes real HttpTransport calls against `settings.internal_api_url`
    exactly as it would against a sibling `api` container in production --
    pointing that setting at this real local server (instead of mocking the
    transport layer) tests the actual production code path unmodified.
    """
    import asyncio

    import uvicorn

    from app.main import app as fastapi_app

    port = _free_port()
    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)

    yield f"http://127.0.0.1:{port}/v1"

    server.should_exit = True
    await task


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


@pytest.mark.asyncio
async def test_pipeline_runs_to_completion(
    workspace_http_client,
    auth_headers,
    engine,
    internal_api_url,
    fake_openai,
):
    import os

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import worker
    from app.config import get_settings
    from app.models import Computation, Job, JobEvent, Run

    os.environ["INTERNAL_API_URL"] = internal_api_url
    get_settings.cache_clear()

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "research today's AI infrastructure news"},
        headers=auth_headers,
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    claimed = await worker._claim_next_job(session_factory)
    assert claimed is not None and claimed.id == job_id

    await worker._run_one(session_factory, claimed)

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
            "extract_facts",
            "research_background",
            "analyze",
            "write_draft",
            "fact_check",
        }
        assert {c["name"]: c["artifact_type"] for c in computations}["extract_facts"] == "fact"
        assert {c["name"]: c["artifact_type"] for c in computations}["fact_check"] is None

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
            + ["STEP_STARTED", "STEP_FINISHED"] * 5
            + ["SUCCEEDED"]
        )


@pytest.mark.asyncio
async def test_pipeline_stops_when_job_is_cancelled_mid_pipeline(
    workspace_http_client, auth_headers, engine, internal_api_url, fake_openai, monkeypatch
):
    import os

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import worker
    from app.agent import job_control
    from app.config import get_settings
    from app.models import Job

    os.environ["INTERNAL_API_URL"] = internal_api_url
    get_settings.cache_clear()

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
        if event_type == "STEP_FINISHED" and call_count >= 4:  # after 2 steps
            async with session_factory() as session:
                job = await session.get(Job, job_id_arg)
                job.status = "CANCELLED"
                await session.commit()

    # pipeline.py calls `job_control.emit(...)` as an attribute lookup on
    # the module object each time, so patching it here (the same module
    # object pipeline.py imported) is enough -- no separate patch needed.
    monkeypatch.setattr(job_control, "emit", _emit_then_cancel)

    await worker._run_one(session_factory, claimed)

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        # The pipeline must not clobber the externally-set CANCELLED status
        # back to SUCCEEDED.
        assert job.status == "CANCELLED"


@pytest.mark.asyncio
async def test_pipeline_stops_when_cost_cap_reached(
    workspace_http_client, auth_headers, engine, internal_api_url, fake_openai
):
    import os

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import worker
    from app.config import get_settings
    from app.models import Computation, Job

    os.environ["INTERNAL_API_URL"] = internal_api_url
    get_settings.cache_clear()

    # First step costs $0.05; the job's cap ($0.03, set below) is exceeded
    # after it, so the guard before step 2 must stop the pipeline there.
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
    await worker._run_one(session_factory, claimed)

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "FAILED"
        assert job.error_message == "cost cap reached"
        assert float(job.spent_usd) == pytest.approx(0.05)

        # The one artifact already produced stays -- and reusable -- even
        # though the job overall failed on cost.
        computations = (
            await session.execute(
                Computation.__table__.select().where(Computation.run_id == job.run_id)
            )
        ).mappings().all()
        assert len(computations) == 1
        assert computations[0]["name"] == "extract_facts"
        assert computations[0]["status"] == "SUCCEEDED"
        assert computations[0]["reusable"] is True


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
