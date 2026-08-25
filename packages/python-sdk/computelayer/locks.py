"""Stampede prevention (spec §37).

If ten processes request the same uncached fingerprint at once, only one should
execute.  The winner takes a lock; the losers wait and then re-run the lookup,
which by then returns ``HIT``.

Correctness must not depend on Redis: every failure mode here degrades to
"just execute", which is slower but never wrong.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Protocol

__all__ = ["LockHandle", "StampedeLock", "NullLock", "AsyncioLock", "RedisLock"]

DEFAULT_LOCK_TTL_SECONDS = 60


class LockHandle:
    """Result of an acquire attempt."""

    def __init__(self, acquired: bool, release: Any = None) -> None:
        self.acquired = acquired
        self._release = release

    async def release(self) -> None:
        if self._release is not None:
            await self._release()
            self._release = None


class StampedeLock(Protocol):
    async def acquire(self, key: str, ttl_seconds: int) -> LockHandle: ...


class NullLock:
    """No coordination -- every caller executes."""

    async def acquire(self, key: str, ttl_seconds: int) -> LockHandle:
        return LockHandle(acquired=True)


class AsyncioLock:
    """Single-process coordination, enough for one agent with parallel branches."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    async def acquire(self, key: str, ttl_seconds: int) -> LockHandle:
        lock = self._locks.setdefault(key, asyncio.Lock())
        if lock.locked():
            return LockHandle(acquired=False)
        await lock.acquire()

        async def _release() -> None:
            if lock.locked():
                lock.release()

        return LockHandle(acquired=True, release=_release)


class RedisLock:
    """Cross-process lock: ``SET key token NX EX ttl`` (§37).

    Released with a compare-and-delete Lua script so a lock that already
    expired and was re-acquired by someone else is never deleted by the
    previous holder.
    """

    _RELEASE_SCRIPT = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    else
        return 0
    end
    """

    def __init__(self, redis: Any, *, namespace: str = "computelayer") -> None:
        self._redis = redis
        self._namespace = namespace

    def _key(self, key: str) -> str:
        return f"lock:{self._namespace}:{key}"

    async def acquire(
        self, key: str, ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS
    ) -> LockHandle:
        redis_key = self._key(key)
        token = uuid.uuid4().hex
        try:
            acquired = await self._redis.set(redis_key, token, nx=True, ex=ttl_seconds)
        except Exception:
            # Redis unavailable -- fall back to execution (§37).
            return LockHandle(acquired=True)

        if not acquired:
            return LockHandle(acquired=False)

        async def _release() -> None:
            try:
                await self._redis.eval(self._RELEASE_SCRIPT, 1, redis_key, token)
            except Exception:
                pass  # the TTL will clean it up

        return LockHandle(acquired=True, release=_release)
