"""Verify a Supabase-issued end-user session JWT (V0.2 human-workspace slice).

Supabase's own guidance recommends against the legacy shared-secret (HS256)
verification approach; current projects sign with an asymmetric key (ES256)
published at ``<project>/auth/v1/.well-known/jwks.json``. This module
verifies against that JWKS endpoint -- no shared secret is configured or
needed. Identity only: this module never touches the database. Mapping a
verified token onto the app's own users/workspaces lives in
``app.services.user_scope``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient

from app.config import get_settings

logger = logging.getLogger("computelayer.api")

__all__ = ["SupabaseClaims", "verify_supabase_jwt", "bearer_token"]


@dataclass(frozen=True)
class SupabaseClaims:
    supabase_user_id: str
    email: str


@lru_cache
def _jwks_client(supabase_url: str) -> PyJWKClient:
    # PyJWKClient caches the fetched key set in-process; Supabase's own edge
    # cache in front of the endpoint is 10 minutes, so no extra TTL logic is
    # needed here.
    return PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization.split(" ", 1)[1].strip()


def verify_supabase_jwt(token: str) -> SupabaseClaims:
    settings = get_settings()
    if not settings.supabase_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="human workspace auth is not configured",
        )

    try:
        signing_key = _jwks_client(settings.supabase_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
        )
    except jwt.PyJWTError as exc:
        logger.info("rejected session token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="session token missing sub/email claims",
        )
    return SupabaseClaims(supabase_user_id=sub, email=email)
