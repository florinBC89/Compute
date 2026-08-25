"""The ComputeLayer client (spec §7)."""

from __future__ import annotations

import os
from types import TracebackType
from typing import Any

from computelayer.compute import Compute
from computelayer.context import set_current_run_id
from computelayer.dependency import Dependency, dep as _dep
from computelayer.errors import ConfigurationError
from computelayer.locks import AsyncioLock, RedisLock, StampedeLock
from computelayer.secrets import Secret, secret as _secret
from computelayer.transport import DEFAULT_BASE_URL, HttpTransport

__all__ = ["ComputeLayer"]


class ComputeLayer:
    """Entry point::

        from computelayer import ComputeLayer

        cl = ComputeLayer(api_key="cl_test_...", project="research-agent")

    Pass ``local=True`` for an in-memory backend with no API, Postgres or Redis
    -- useful in unit tests and offline development.
    """

    def __init__(
        self,
        api_key: str | None = None,
        project: str | None = None,
        *,
        base_url: str | None = None,
        transport: Any = None,
        local: bool = False,
        redis: Any = None,
        code_version: str | None = None,
        store_inputs: bool = True,
        store_outputs: bool = True,
        lock_wait_seconds: float = 30.0,
        timeout: float = 30.0,
    ) -> None:
        self.project = project or os.getenv("COMPUTELAYER_PROJECT") or "default"
        self.api_key = api_key or os.getenv("COMPUTELAYER_API_KEY")
        self.base_url = (
            base_url or os.getenv("COMPUTELAYER_API_URL") or DEFAULT_BASE_URL
        )
        self.code_version = code_version
        self.store_inputs = store_inputs
        self.store_outputs = store_outputs
        self.lock_wait_seconds = lock_wait_seconds

        if transport is not None:
            self.transport = transport
        elif local:
            from computelayer.testing import LocalBackend

            self.transport = LocalBackend(project=self.project)
        else:
            if not self.api_key:
                raise ConfigurationError(
                    "api_key is required. Pass api_key=..., set "
                    "COMPUTELAYER_API_KEY, or use ComputeLayer(local=True)."
                )
            self.transport = HttpTransport(
                api_key=self.api_key,
                base_url=self.base_url,
                project=self.project,
                timeout=timeout,
            )

        self.lock: StampedeLock
        if redis is not None:
            self.lock = RedisLock(redis, namespace=self.project)
        elif local or transport is not None:
            self.lock = AsyncioLock()
        else:
            # Without Redis, cross-process coordination is impossible; executing
            # twice is wasteful but never incorrect (§37).
            self.lock = AsyncioLock()

        self.compute = Compute(self)

    # -- helpers exposed on the client ------------------------------------

    def dep(
        self,
        key: str,
        version: str | None = None,
        *,
        content: Any = None,
        type: str = "MANUAL",
    ) -> Dependency:
        """Build a dependency (§11)."""
        return _dep(key, version, content=content, type=type)

    def secret(self, value: Any) -> Secret:
        """Wrap a sensitive input so it hashes but is never stored (§57)."""
        return _secret(value)

    # -- resources (§33) ---------------------------------------------------

    async def upsert_resource(
        self,
        resource_key: str,
        version: str | None = None,
        *,
        content: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record the current version of external state.

        Returns ``{"changed": bool, "previous_version": ..., "current_version": ...}``.
        """
        dependency = _dep(resource_key, version, content=content, type="EXTERNAL")
        return await self.transport.upsert_resource(
            {
                "resource_key": resource_key,
                "version": dependency.version,
                "metadata": metadata or {},
            }
        )

    # -- runs ---------------------------------------------------------------

    def run(
        self,
        *,
        external_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "_RunContext":
        """Group computations into one agent invocation (§6.3)::

            async with cl.run() as run:
                ...
            print(run.summary)
        """
        return _RunContext(self, external_run_id=external_run_id, metadata=metadata)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        return await self.transport.get_run(run_id)

    async def get_run_graph(self, run_id: str) -> dict[str, Any]:
        return await self.transport.get_run_graph(run_id)

    async def get_metrics(self, period: str = "30d") -> dict[str, Any]:
        return await self.transport.get_metrics(period)

    async def explain(self, computation_id: str) -> dict[str, Any]:
        """Why did this computation run? (§53)"""
        explain = getattr(self.transport, "explain", None)
        if explain is None:
            raise ConfigurationError("this transport does not support explain()")
        return await explain(computation_id)

    # -- lifecycle ----------------------------------------------------------

    async def aclose(self) -> None:
        await self.transport.aclose()

    async def __aenter__(self) -> "ComputeLayer":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()


class _RunContext:
    """Async context manager that opens and closes a run."""

    def __init__(
        self,
        client: ComputeLayer,
        *,
        external_run_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        self._client = client
        self._external_run_id = external_run_id
        self._metadata = metadata or {}
        self._token: Any = None
        self.id: str = ""
        self.summary: dict[str, Any] = {}

    async def __aenter__(self) -> "_RunContext":
        created = await self._client.transport.create_run(
            {
                "external_run_id": self._external_run_id,
                "metadata": self._metadata,
            }
        )
        self.id = created["id"]
        self._token = set_current_run_id(self.id)
        self._token.__enter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._token is not None:
            self._token.__exit__(exc_type, exc, tb)
        status = "FAILED" if exc_type is not None else "SUCCEEDED"
        self.summary = await self._client.transport.finish_run(
            self.id, {"status": status}
        )

    async def graph(self) -> dict[str, Any]:
        return await self._client.transport.get_run_graph(self.id)
