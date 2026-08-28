"""Supabase-session auth: JWT verification, first-login provisioning,
idempotency (V0.2 human-workspace slice, Phase 1).

JWKS verification itself was proven live against a real Supabase project
(the JWKS endpoint was fetched over the network and correctly rejected a
well-formed-but-unsigned token). These tests exercise the success path with
a self-signed token so they run offline and deterministically in CI: a fake
JWKS client stands in for the network fetch, but every other step --
signature algorithm, claim checks, first-login provisioning, idempotency --
runs for real against the real Postgres schema.
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


def _make_token(keypair, *, sub: str, email: str, **overrides) -> str:
    private_key, _ = keypair
    payload = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "iss": ISSUER,
        "exp": 9_999_999_999,
        **overrides,
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": KID})


@pytest_asyncio.fixture
async def workspace_http_client(engine, keypair, monkeypatch):
    """Like conftest's ``http_client``, but unauthenticated (Supabase JWTs
    are supplied per-request) and with the JWKS fetch stubbed to this
    fixture's own keypair instead of a real network call.
    """
    os.environ["SUPABASE_URL"] = SUPABASE_URL
    from app.config import get_settings

    get_settings.cache_clear()

    _, public_key = keypair

    class _FakeSigningKey:
        def __init__(self, key):
            self.key = key

    class _FakeJWKClient:
        def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
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


@pytest.mark.asyncio
async def test_first_login_provisions_workspace(workspace_http_client, keypair):
    sub = str(uuid.uuid4())
    token = _make_token(keypair, sub=sub, email="researcher@example.com")

    response = await workspace_http_client.get(
        "/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "researcher@example.com"
    assert body["workspace_name"] == "researcher@example.com"
    assert body["projects"] == []
    assert uuid.UUID(body["workspace_id"])


@pytest.mark.asyncio
async def test_repeat_login_reuses_the_same_workspace(workspace_http_client, keypair):
    sub = str(uuid.uuid4())
    token = _make_token(keypair, sub=sub, email="repeat@example.com")

    first = await workspace_http_client.get(
        "/me", headers={"Authorization": f"Bearer {token}"}
    )
    second = await workspace_http_client.get(
        "/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert first.json()["workspace_id"] == second.json()["workspace_id"]
    assert first.json()["user_id"] == second.json()["user_id"]


@pytest.mark.asyncio
async def test_two_users_get_two_workspaces(workspace_http_client, keypair):
    token_a = _make_token(keypair, sub=str(uuid.uuid4()), email="a@example.com")
    token_b = _make_token(keypair, sub=str(uuid.uuid4()), email="b@example.com")

    response_a = await workspace_http_client.get(
        "/me", headers={"Authorization": f"Bearer {token_a}"}
    )
    response_b = await workspace_http_client.get(
        "/me", headers={"Authorization": f"Bearer {token_b}"}
    )

    assert response_a.json()["workspace_id"] != response_b.json()["workspace_id"]


@pytest.mark.asyncio
async def test_wrong_audience_is_rejected(workspace_http_client, keypair):
    token = _make_token(
        keypair, sub=str(uuid.uuid4()), email="x@example.com", aud="some-other-audience"
    )

    response = await workspace_http_client.get(
        "/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_is_rejected(workspace_http_client, keypair):
    token = _make_token(keypair, sub=str(uuid.uuid4()), email="x@example.com", exp=1)

    response = await workspace_http_client.get(
        "/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_bearer_token_is_rejected(workspace_http_client):
    response = await workspace_http_client.get("/me")
    assert response.status_code == 401
