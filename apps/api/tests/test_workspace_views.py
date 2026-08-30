"""Workspace-scoped project/run views (V0.2 human-workspace slice, Phases
6 and 8; V0.3 chat-turns slice, Phase 0).

Covers the same numbers the developer dashboard's project-slug routes
already report (app.services.artifacts/app.services.runs/app.services.
cross_model are shared), plus the ownership check that's unique to this
surface: a project or run belonging to a *different* workspace must 404,
not leak data. Also covers the turn-history route backing the chat thread
(app.services.jobs.list_project_jobs) -- a project's jobs, oldest first.
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
async def seeded_run(engine, workspace_http_client, auth_headers):
    """A real project (via POST /jobs's default-project provisioning), a run
    and two computations -- one classified as an artifact, one not -- owned
    by this fixture's authenticated user.
    """
    from sqlalchemy import select

    from app.models import Computation, Project, Run

    await workspace_http_client.post(
        "/jobs", json={"task_text": "seed a project"}, headers=auth_headers
    )
    me = await workspace_http_client.get("/me", headers=auth_headers)
    workspace_id = uuid.UUID(me.json()["workspace_id"])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id)
            )
        ).scalars().first()
        project_id = project.id

        run = Run(id=uuid.uuid4(), workspace_id=workspace_id, project_id=project_id, status="SUCCEEDED")
        session.add(run)
        await session.flush()

        session.add(
            Computation(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                project_id=project_id,
                run_id=run.id,
                name="extract_facts",
                logical_key="a" * 64,
                fingerprint="b" * 64,
                status="SUCCEEDED",
                cache_status="MISS",
                artifact_type="fact",
                model="openai/gpt-4o-mini",
                model_agnostic_fingerprint="e" * 64,
                cost_usd=0.001,
                input_tokens=10,
                output_tokens=10,
            )
        )
        session.add(
            Computation(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                project_id=project_id,
                run_id=run.id,
                name="fact_check",
                logical_key="c" * 64,
                fingerprint="d" * 64,
                status="SUCCEEDED",
                cache_status="MISS",
                artifact_type=None,
                cost_usd=0.0005,
                input_tokens=5,
                output_tokens=5,
            )
        )
        await session.commit()

    return {"project_id": project_id, "run_id": run.id}


@pytest_asyncio.fixture
async def auth_headers(workspace_http_client, keypair):
    token = _make_token(keypair, sub=str(uuid.uuid4()), email="researcher@example.com")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_project_artifacts_returns_only_classified_computations(
    workspace_http_client, auth_headers, seeded_run
):
    response = await workspace_http_client.get(
        f"/workspace/projects/{seeded_run['project_id']}/artifacts", headers=auth_headers
    )

    assert response.status_code == 200
    artifacts = response.json()["artifacts"]
    assert [a["name"] for a in artifacts] == ["extract_facts"]
    assert artifacts[0]["artifact_type"] == "fact"


@pytest.mark.asyncio
async def test_run_summary_reports_real_totals(
    workspace_http_client, auth_headers, seeded_run
):
    response = await workspace_http_client.get(
        f"/workspace/runs/{seeded_run['run_id']}", headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUCCEEDED"
    assert body["computations"] == 2
    assert body["total_cost_usd"] == pytest.approx(0.0015)


@pytest.mark.asyncio
async def test_run_graph_lists_nodes(workspace_http_client, auth_headers, seeded_run):
    response = await workspace_http_client.get(
        f"/workspace/runs/{seeded_run['run_id']}/graph", headers=auth_headers
    )

    assert response.status_code == 200
    names = {n["name"] for n in response.json()["nodes"]}
    assert names == {"extract_facts", "fact_check"}


@pytest.mark.asyncio
async def test_project_jobs_lists_turns_in_order(
    workspace_http_client, auth_headers, seeded_run
):
    """V0.3 Phase 0: a project's turn history is just its jobs, oldest
    first -- seeded_run's own setup already created one ("seed a
    project"); two more here prove ordering, not just presence.

    V0.3 conversation history: project_id must be passed explicitly to
    land in the SAME conversation -- omitting it now creates a brand-new
    project per call (each job with no project_id starts its own
    conversation), so these two use seeded_run's project_id on purpose.
    """
    await workspace_http_client.post(
        "/jobs",
        json={"task_text": "second turn", "project_id": str(seeded_run["project_id"])},
        headers=auth_headers,
    )
    await workspace_http_client.post(
        "/jobs",
        json={"task_text": "third turn", "project_id": str(seeded_run["project_id"])},
        headers=auth_headers,
    )

    response = await workspace_http_client.get(
        f"/workspace/projects/{seeded_run['project_id']}/jobs", headers=auth_headers
    )

    assert response.status_code == 200
    jobs = response.json()["jobs"]
    assert [j["task_text"] for j in jobs] == ["seed a project", "second turn", "third turn"]
    assert all(j["project_id"] == str(seeded_run["project_id"]) for j in jobs)
    # None of these jobs has run yet -- no answer_text yet either.
    assert all(j["answer_text"] is None for j in jobs)


@pytest.mark.asyncio
async def test_project_jobs_from_another_workspace_is_not_found(
    workspace_http_client, keypair, seeded_run
):
    other_token = _make_token(keypair, sub=str(uuid.uuid4()), email="other@example.com")
    response = await workspace_http_client.get(
        f"/workspace/projects/{seeded_run['project_id']}/jobs",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_me_lists_projects_most_recent_first(workspace_http_client, auth_headers):
    """V0.3 conversation history: the sidebar's "Recent" list reads
    me.projects in order, so GET /me must return most-recently-created
    first -- not the unordered default a bare query would give.
    """
    first = await workspace_http_client.post(
        "/jobs", json={"task_text": "older conversation"}, headers=auth_headers
    )
    second = await workspace_http_client.post(
        "/jobs", json={"task_text": "newer conversation"}, headers=auth_headers
    )

    me = await workspace_http_client.get("/me", headers=auth_headers)
    project_ids = [p["id"] for p in me.json()["projects"]]
    assert project_ids == [second.json()["project_id"], first.json()["project_id"]]


@pytest.mark.asyncio
async def test_project_from_another_workspace_is_not_found(
    workspace_http_client, keypair, seeded_run
):
    other_token = _make_token(keypair, sub=str(uuid.uuid4()), email="other@example.com")
    response = await workspace_http_client.get(
        f"/workspace/projects/{seeded_run['project_id']}/artifacts",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_run_from_another_workspace_is_not_found(
    workspace_http_client, keypair, seeded_run
):
    other_token = _make_token(keypair, sub=str(uuid.uuid4()), email="other@example.com")
    response = await workspace_http_client.get(
        f"/workspace/runs/{seeded_run['run_id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_preview_model_switch_reuses_portable_artifact_and_recomputes_unclassified(
    workspace_http_client, auth_headers, seeded_run
):
    """extract_facts (artifact_type="fact", a real model_agnostic_fingerprint,
    default-portable) should preview as REUSE against a different target
    model; fact_check (artifact_type=None) can never be a cross-model
    source and must preview as RECOMPUTE.
    """
    response = await workspace_http_client.post(
        f"/workspace/runs/{seeded_run['run_id']}/preview-model-switch",
        json={"target_model": "anthropic/claude-haiku-4-5"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    by_name = {item["name"]: item for item in body["items"]}

    assert by_name["extract_facts"]["decision"] == "REUSE"
    assert by_name["extract_facts"]["cost_if_recomputed_usd"] == 0.0

    assert by_name["fact_check"]["decision"] == "RECOMPUTE"
    assert "not classified" in by_name["fact_check"]["reason"]

    assert body["reusable_count"] == 1
    assert body["recompute_count"] == 1
    # fact_check's own recorded cost (0.0005) is what recomputing it costs.
    assert body["estimated_incremental_cost_usd"] == pytest.approx(0.0005)


@pytest.mark.asyncio
async def test_preview_model_switch_from_another_workspace_is_not_found(
    workspace_http_client, keypair, seeded_run
):
    other_token = _make_token(keypair, sub=str(uuid.uuid4()), email="other@example.com")
    response = await workspace_http_client.post(
        f"/workspace/runs/{seeded_run['run_id']}/preview-model-switch",
        json={"target_model": "anthropic/claude-haiku-4-5"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 404
