"""Ethicals API (Agent OS V0.4 slice, "give Ethical a name and a face").

Covers create -> appears in list -> detail shows work items derived from
the linked project's jobs, plus the ownership check every workspace-scoped
surface needs: an Ethical belonging to a *different* workspace must 404.
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


@pytest_asyncio.fixture
async def seeded_project(workspace_http_client, auth_headers):
    """A real project (via POST /jobs's default-project provisioning), owned
    by this fixture's authenticated user.
    """
    await workspace_http_client.post(
        "/jobs", json={"task_text": "seed a project"}, headers=auth_headers
    )
    me = await workspace_http_client.get("/me", headers=auth_headers)
    return me.json()["projects"][0]["id"]


@pytest.mark.asyncio
async def test_create_ethical_then_appears_in_list(
    workspace_http_client, auth_headers, seeded_project
):
    create = await workspace_http_client.post(
        "/ethicals",
        json={"name": "Research Ethical", "goal": "Track competitor pricing", "project_id": seeded_project},
        headers=auth_headers,
    )
    assert create.status_code == 200
    body = create.json()
    assert body["name"] == "Research Ethical"
    assert body["goal"] == "Track competitor pricing"
    assert body["status"] == "active"
    assert body["project_id"] == seeded_project

    listing = await workspace_http_client.get("/ethicals", headers=auth_headers)
    assert listing.status_code == 200
    assert [a["id"] for a in listing.json()["ethicals"]] == [body["id"]]


@pytest.mark.asyncio
async def test_ethical_detail_reports_work_from_its_project_jobs(
    workspace_http_client, auth_headers, seeded_project
):
    create = await workspace_http_client.post(
        "/ethicals",
        json={"name": "Research Ethical", "project_id": seeded_project},
        headers=auth_headers,
    )
    ethical_id = create.json()["id"]

    detail = await workspace_http_client.get(f"/ethicals/{ethical_id}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    # seeded_project already has the one job created by the fixture, still
    # QUEUED (no run_id yet) -- unclassified reuse.
    assert [w["task_text"] for w in body["work"]] == ["seed a project"]
    assert body["work"][0]["reuse_label"] is None


@pytest.mark.asyncio
async def test_patch_ethical_renames(workspace_http_client, auth_headers, seeded_project):
    create = await workspace_http_client.post(
        "/ethicals",
        json={"name": "Research Ethical", "project_id": seeded_project},
        headers=auth_headers,
    )
    ethical_id = create.json()["id"]

    patched = await workspace_http_client.patch(
        f"/ethicals/{ethical_id}", json={"name": "Renamed Ethical"}, headers=auth_headers
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Renamed Ethical"


@pytest.mark.asyncio
async def test_ethical_from_another_workspace_is_not_found(
    workspace_http_client, keypair, auth_headers, seeded_project
):
    create = await workspace_http_client.post(
        "/ethicals",
        json={"name": "Research Ethical", "project_id": seeded_project},
        headers=auth_headers,
    )
    ethical_id = create.json()["id"]

    other_token = _make_token(keypair, sub=str(uuid.uuid4()), email="other@example.com")
    response = await workspace_http_client.get(
        f"/ethicals/{ethical_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_ethical_for_unowned_project_is_not_found(
    workspace_http_client, keypair, auth_headers, seeded_project
):
    other_token = _make_token(keypair, sub=str(uuid.uuid4()), email="other@example.com")
    response = await workspace_http_client.post(
        "/ethicals",
        json={"name": "Research Ethical", "project_id": seeded_project},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 404
