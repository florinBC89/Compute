"""Server-side Redis helpers (spec §37).

The SDK takes the stampede lock itself, but the API exposes the same Redis
connection for the optional hot cache and for operational tooling.  Redis is an
optimization only: every helper here degrades to a no-op when it is unreachable,
because correctness must not depend on it.
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings

_redis: Any = None


async def get_redis() -> Any | None:
    global _redis
    settings = get_settings()
    if not settings.redis_url:
        return None
    if _redis is None:
        try:
            import redis.asyncio as aioredis
        except ImportError:
            return None
        try:
            _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            await _redis.ping()
        except Exception:
            _redis = None
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:
            pass
    _redis = None
