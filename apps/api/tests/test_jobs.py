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


@pytest.mark.asyncio
async def test_worker_runs_stub_pipeline_to_completion(
    workspace_http_client, auth_headers, engine, monkeypatch
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import worker
    from app.models import Job, JobEvent

    monkeypatch.setattr(worker, "STEP_DURATION_SECONDS", 0)

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "quick job"}, headers=auth_headers
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    claimed = await worker._claim_next_job(session_factory)
    assert claimed is not None and claimed.id == job_id

    await worker.run_stub_pipeline(session_factory, claimed)

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "SUCCEEDED"
        assert job.current_step is None
        assert job.finished_at is not None

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
        assert event_types == [
            "QUEUED",
            "STARTED",
            "STEP_STARTED",
            "STEP_FINISHED",
            "STEP_STARTED",
            "STEP_FINISHED",
            "STEP_STARTED",
            "STEP_FINISHED",
            "SUCCEEDED",
        ]


@pytest.mark.asyncio
async def test_worker_stops_when_job_is_cancelled_mid_pipeline(
    workspace_http_client, auth_headers, engine, monkeypatch
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import worker
    from app.models import Job

    monkeypatch.setattr(worker, "STEP_DURATION_SECONDS", 0)

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "cancel mid-flight"}, headers=auth_headers
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    claimed = await worker._claim_next_job(session_factory)

    original_emit = worker._emit
    call_count = 0

    async def _emit_then_cancel(session_factory, job_id_arg, event_type, payload=None):
        nonlocal call_count
        call_count += 1
        await original_emit(session_factory, job_id_arg, event_type, payload)
        if event_type == "STEP_FINISHED" and call_count >= 4:
            async with session_factory() as session:
                job = await session.get(Job, job_id_arg)
                job.status = "CANCELLED"
                await session.commit()

    monkeypatch.setattr(worker, "_emit", _emit_then_cancel)

    await worker.run_stub_pipeline(session_factory, claimed)

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        # The worker must not clobber the externally-set CANCELLED status
        # back to SUCCEEDED.
        assert job.status == "CANCELLED"


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
