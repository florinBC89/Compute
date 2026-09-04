"""One streamed chat turn (V0.3 chat component) + the new GET
/jobs/{id}/stream route.

Duplicates the fixture set test_jobs.py already defines (keypair/
workspace_http_client/auth_headers) rather than centralizing them into
conftest.py, matching this codebase's established per-test-file convention
-- see test_jobs.py's own module docstring/fixtures for the reasoning.

Covers: the delta-then-sentinel shape of app.agent.chat.run_chat_turn's
`delta_queue` output (a), the cache-HIT proof that regenerating an
identical turn calls the provider's streaming API zero additional times
(b), that a FAILED turn is excluded from app.services.jobs.build_chat_history
(c), and the new GET /jobs/{id}/stream route end to end (d) -- with the
LLM calls mocked (fake_openai_stream) so this suite runs free and
deterministically, the same as every other test file in this repo.
"""

from __future__ import annotations

import asyncio
import json
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
    token = _make_token(keypair, sub=str(uuid.uuid4()), email="chatter@example.com")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def chat_transport_factory(workspace_http_client):
    """Same shape as test_jobs.py's pipeline_transport_factory -- a
    `transport_factory` seam (see app.agent.chat.run_chat_turn's own
    docstring) that binds the SDK straight to this test's in-process ASGI
    app instead of a real socket. Used by tests that call
    chat.run_chat_turn directly.
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
async def internal_api_asgi_transport(monkeypatch, workspace_http_client):
    """The new GET /jobs/{id}/stream route (unlike run_research_pipeline's
    call sites in test_jobs.py) calls app.agent.chat.run_chat_turn WITHOUT
    a transport_factory -- production always talks to
    settings.internal_api_url over a real socket, and the route doesn't
    expose a test seam for that (see app.routes.jobs.stream_chat_turn).

    So that an end-to-end test of the route doesn't need a real listening
    server, this patches `httpx.AsyncClient` itself for the duration of one
    test: computelayer.transport.HttpTransport lazily builds its own
    httpx.AsyncClient the first time it actually needs one (see
    HttpTransport._ensure_client), with no `transport=` override in that
    path -- forcing every such client onto this test's in-process ASGI app
    (`app.main.app`, the same app workspace_http_client itself already
    talks to) is what lets the route's real (non-test-seamed) ComputeLayer
    construction still avoid a real network call.
    """
    import httpx as httpx_module
    from httpx import ASGITransport as _ASGITransport

    from app.main import app as fastapi_app

    _RealAsyncClient = httpx_module.AsyncClient

    class _ASGIBoundAsyncClient(_RealAsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = _ASGITransport(app=fastapi_app)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx_module, "AsyncClient", _ASGIBoundAsyncClient)


@pytest_asyncio.fixture
async def fake_openai_stream(monkeypatch):
    """Patches both openai_provider.stream_complete (the chat turn itself)
    and openai_provider.complete (turn_common.maybe_title_project's own,
    separate, non-streaming call -- always openai regardless of
    model_preference, see turn_common.py) -- a chat turn on a project's
    first job always runs concurrently with a possible title-gen call, so
    both need faking for a test to stay free and deterministic. Mirrors
    test_jobs.py's own fake_openai in shape (same LLMCall/record_llm_call
    usage, so Compute.run()'s cost ledger works exactly as it would for a
    real call).

    Returns `(stream_calls, chunks)`: `stream_calls["n"]` counts
    stream_complete invocations (the cache-HIT proof checks this stays put
    across a regenerate), `chunks` is the fixed list of fake text chunks
    each stream_complete call pushes to `on_delta`, in order.
    """
    from app.agent.providers import openai as openai_provider
    from computelayer.context import LLMCall, record_llm_call

    stream_calls = {"n": 0}
    chunks = ["Hello", ", world!"]

    async def _fake_stream_complete(
        *, system: str, history: list[dict[str, str]], message: str, max_tokens: int = 400, on_delta
    ) -> str:
        stream_calls["n"] += 1
        for chunk in chunks:
            await on_delta(chunk)
        record_llm_call(
            LLMCall(
                model=openai_provider.MODEL,
                provider="openai",
                input_tokens=50,
                output_tokens=50,
                cost_usd=0.001,
                latency_ms=5,
            )
        )
        return "".join(chunks)

    async def _fake_complete(*, system: str, prompt: str, max_tokens: int = 400) -> str:
        record_llm_call(
            LLMCall(
                model=openai_provider.MODEL,
                provider="openai",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.0001,
                latency_ms=5,
            )
        )
        return "Fake Title"

    monkeypatch.setattr(openai_provider, "stream_complete", _fake_stream_complete)
    monkeypatch.setattr(openai_provider, "complete", _fake_complete)
    return stream_calls, chunks


@pytest_asyncio.fixture
async def fake_anthropic_stream(monkeypatch):
    """Same shape as fake_openai_stream, for the anthropic provider module."""
    from app.agent.providers import anthropic as anthropic_provider
    from computelayer.context import LLMCall, record_llm_call

    stream_calls = {"n": 0}
    chunks = ["Hi", " there!"]

    async def _fake_stream_complete(
        *, system: str, history: list[dict[str, str]], message: str, max_tokens: int = 400, on_delta
    ) -> str:
        stream_calls["n"] += 1
        for chunk in chunks:
            await on_delta(chunk)
        record_llm_call(
            LLMCall(
                model=anthropic_provider.MODEL,
                provider="anthropic",
                input_tokens=50,
                output_tokens=50,
                cost_usd=0.001,
                latency_ms=5,
            )
        )
        return "".join(chunks)

    monkeypatch.setattr(anthropic_provider, "stream_complete", _fake_stream_complete)
    return stream_calls, chunks


@pytest_asyncio.fixture
async def fake_gemini_stream(monkeypatch):
    """Same shape as fake_openai_stream, for the gemini provider module."""
    from app.agent.providers import gemini as gemini_provider
    from computelayer.context import LLMCall, record_llm_call

    stream_calls = {"n": 0}
    chunks = ["Sure", ", here you go."]

    async def _fake_stream_complete(
        *, system: str, history: list[dict[str, str]], message: str, max_tokens: int = 400, on_delta
    ) -> str:
        stream_calls["n"] += 1
        for chunk in chunks:
            await on_delta(chunk)
        record_llm_call(
            LLMCall(
                model=gemini_provider.MODEL,
                provider="gemini",
                input_tokens=50,
                output_tokens=50,
                cost_usd=0.001,
                latency_ms=5,
            )
        )
        return "".join(chunks)

    monkeypatch.setattr(gemini_provider, "stream_complete", _fake_stream_complete)
    return stream_calls, chunks


@pytest.mark.asyncio
async def test_chat_turn_streams_deltas_then_sentinel(
    workspace_http_client,
    auth_headers,
    engine,
    chat_transport_factory,
    fake_openai_stream,
):
    from app.agent import chat
    from app.models import Job
    from app.routes import jobs as jobs_route

    stream_calls, chunks = fake_openai_stream

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "say hello"}, headers=auth_headers
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        claimed = await jobs_route._claim_chat_turn(session, job_id)
    assert claimed is not None

    delta_queue: asyncio.Queue = asyncio.Queue()
    turn_task = asyncio.create_task(
        chat.run_chat_turn(
            claimed,
            session_factory,
            delta_queue=delta_queue,
            transport_factory=chat_transport_factory,
        )
    )

    # Consume exactly the way app.routes.jobs's /stream route does: collect
    # items until the first None sentinel.
    items = []
    while True:
        item = await delta_queue.get()
        items.append(item)
        if item is None:
            break
    await turn_task  # let the turn fully finish (key deactivation, title_task, ...)

    assert items[-1] is None
    deltas = [item["text"] for item in items if item is not None and item["type"] == "delta"]
    assert deltas == chunks
    assert stream_calls["n"] == 1

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "SUCCEEDED"
        assert job.answer_text == "".join(chunks)


@pytest.mark.asyncio
async def test_regenerating_identical_message_is_a_cache_hit(
    workspace_http_client,
    auth_headers,
    engine,
    chat_transport_factory,
    fake_openai_stream,
):
    """The cache-HIT proof (spec's core mechanism): re-running the exact
    same turn (same job, same task_text, same -- empty -- history, since
    build_chat_history excludes the job being processed from its own
    history) must be served straight from the reuse engine: zero
    additional stream_complete calls, and delta_queue receives nothing but
    the sentinel, because fn() is never invoked on a HIT.
    """
    from app.agent import chat
    from app.models import Job
    from app.routes import jobs as jobs_route

    stream_calls, _chunks = fake_openai_stream

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "regenerate me"}, headers=auth_headers
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        claimed = await jobs_route._claim_chat_turn(session, job_id)

    first_queue: asyncio.Queue = asyncio.Queue()
    await chat.run_chat_turn(
        claimed,
        session_factory,
        delta_queue=first_queue,
        transport_factory=chat_transport_factory,
    )
    assert stream_calls["n"] == 1

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "SUCCEEDED"
        # Simulate a "regenerate": re-run the identical turn.
        job.status = "RUNNING"
        await session.commit()
        rerun_job = job

    second_queue: asyncio.Queue = asyncio.Queue()
    await chat.run_chat_turn(
        rerun_job,
        session_factory,
        delta_queue=second_queue,
        transport_factory=chat_transport_factory,
    )

    # The proof: no additional call to the fake provider's streaming API.
    assert stream_calls["n"] == 1

    items = []
    while not second_queue.empty():
        items.append(second_queue.get_nowait())
    # turn_common.maybe_title_project must NOT re-title on the second call:
    # it already emitted PROJECT_TITLED for this exact job.id on the first
    # run, and that JobEvent survives the regenerate reset -- re-firing here
    # would be an unbilled-for-nothing regression this test guards against.
    assert items == [None]

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_lazy_mode_is_part_of_the_cache_fingerprint(
    workspace_http_client,
    auth_headers,
    engine,
    chat_transport_factory,
    monkeypatch,
):
    """Regression guard for app.agent.chat's `inputs` fix: lazy_mode changes
    what the provider is actually asked to produce, so it must be part of
    cl.compute.run()'s fingerprint, not just the `system` string handed to
    the provider -- otherwise the exact same job, re-run with only
    lazy_mode flipped (same task_text, same -- empty -- history), would
    collide on the same cache entry test_regenerating_identical_message_is_a_cache_hit
    proves exists for a genuine regenerate, and silently return the OTHER
    mode's cached answer instead of a fresh call.
    """
    from app.agent import chat
    from app.agent.chat import LAZY_MODE_SYSTEM_SUFFIX
    from app.agent.providers import openai as openai_provider
    from app.models import Job
    from app.routes import jobs as jobs_route
    from computelayer.context import LLMCall, record_llm_call

    seen_systems: list[str] = []

    async def _fake_stream_complete(
        *, system: str, history: list[dict[str, str]], message: str, max_tokens: int = 400, on_delta
    ) -> str:
        seen_systems.append(system)
        await on_delta("ok")
        record_llm_call(
            LLMCall(
                model=openai_provider.MODEL,
                provider="openai",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.0001,
                latency_ms=5,
            )
        )
        return "ok"

    async def _fake_complete(*, system: str, prompt: str, max_tokens: int = 400) -> str:
        record_llm_call(
            LLMCall(
                model=openai_provider.MODEL,
                provider="openai",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.0001,
                latency_ms=5,
            )
        )
        return "Fake Title"

    monkeypatch.setattr(openai_provider, "stream_complete", _fake_stream_complete)
    monkeypatch.setattr(openai_provider, "complete", _fake_complete)

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "write a date picker"}, headers=auth_headers
    )
    job_id = uuid.UUID(created.json()["id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        claimed = await jobs_route._claim_chat_turn(session, job_id)

    await chat.run_chat_turn(
        claimed,
        session_factory,
        delta_queue=asyncio.Queue(),
        transport_factory=chat_transport_factory,
    )
    assert len(seen_systems) == 1

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        job.status = "RUNNING"
        job.lazy_mode = True  # the only thing that changed
        await session.commit()
        rerun_job = job

    await chat.run_chat_turn(
        rerun_job,
        session_factory,
        delta_queue=asyncio.Queue(),
        transport_factory=chat_transport_factory,
    )

    # A genuine second provider call, not a cache hit -- proves lazy_mode is
    # part of the fingerprint, not just the system prompt text.
    assert len(seen_systems) == 2
    assert LAZY_MODE_SYSTEM_SUFFIX not in seen_systems[0]
    assert LAZY_MODE_SYSTEM_SUFFIX in seen_systems[1]


@pytest.mark.asyncio
async def test_failed_turn_excluded_from_chat_history(
    workspace_http_client,
    auth_headers,
    engine,
    chat_transport_factory,
    fake_openai_stream,
    monkeypatch,
):
    from app.agent import chat
    from app.agent.providers import openai as openai_provider
    from app.models import Job
    from app.routes import jobs as jobs_route
    from app.services.jobs import build_chat_history

    async def _broken_stream_complete(
        *, system: str, history: list[dict[str, str]], message: str, max_tokens: int = 400, on_delta
    ) -> str:
        raise RuntimeError("boom")

    # Overrides fake_openai_stream's own stream_complete fake -- .complete
    # (title-gen) stays faked so this test doesn't hit the real API either.
    monkeypatch.setattr(openai_provider, "stream_complete", _broken_stream_complete)

    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "this will fail"}, headers=auth_headers
    )
    job_id = uuid.UUID(created.json()["id"])
    project_id = uuid.UUID(created.json()["project_id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        claimed = await jobs_route._claim_chat_turn(session, job_id)

    delta_queue: asyncio.Queue = asyncio.Queue()
    await chat.run_chat_turn(
        claimed,
        session_factory,
        delta_queue=delta_queue,
        transport_factory=chat_transport_factory,
    )

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job.status == "FAILED"
        assert job.answer_text is None

        # A next turn in the same conversation must not see this failed
        # turn in its history.
        history = await build_chat_history(session, project_id)
        assert history == []


@pytest.mark.asyncio
async def test_stream_endpoint_runs_a_turn_to_completion(
    workspace_http_client,
    auth_headers,
    engine,
    fake_openai_stream,
    internal_api_asgi_transport,
):
    created = await workspace_http_client.post(
        "/jobs", json={"task_text": "stream this end to end"}, headers=auth_headers
    )
    job_id = created.json()["id"]

    lines: list[str] = []
    async with workspace_http_client.stream(
        "GET", f"/jobs/{job_id}/stream", headers=auth_headers
    ) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line:
                lines.append(line)

    assert lines
    last = lines[-1]
    assert last.startswith("data: ")
    payload = json.loads(last[len("data: ") :])
    assert payload["type"] == "done"
    assert payload["job"]["id"] == job_id
    assert payload["job"]["status"] == "SUCCEEDED"
    assert payload["job"]["answer_text"] == "Hello, world!"
