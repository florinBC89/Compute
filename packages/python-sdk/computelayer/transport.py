"""Transport layer: how the SDK talks to the ComputeLayer API (spec §28-§36).

Two implementations ship with V0.1:

``HttpTransport``
    Talks to a running API over HTTPS with a project-scoped bearer key.

``computelayer.testing.LocalBackend``
    An in-process, dependency-free implementation of the same protocol.  It
    exists so unit tests -- and offline development -- exercise the real
    ``compute.run`` code path without Postgres, Redis, or a network.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from computelayer.errors import APIError, TransportError

__all__ = ["Transport", "HttpTransport"]

DEFAULT_BASE_URL = "https://api.computelayer.dev/v1"


@runtime_checkable
class Transport(Protocol):
    """Everything ``compute.run`` needs from the backend."""

    async def lookup(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    async def start(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    async def complete(
        self, computation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def fail(
        self, computation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def upsert_resource(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    async def create_run(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    async def finish_run(
        self, run_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def get_run(self, run_id: str) -> dict[str, Any]: ...

    async def get_run_graph(self, run_id: str) -> dict[str, Any]: ...

    async def get_metrics(self, period: str = "30d") -> dict[str, Any]: ...

    async def aclose(self) -> None: ...


class HttpTransport:
    """``httpx``-backed transport against the REST API (§28)."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        project: str | None = None,
        timeout: float = 30.0,
        client: Any = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.project = project
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    # -- plumbing ---------------------------------------------------------

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                import httpx
            except ImportError as exc:  # pragma: no cover - import guard
                raise TransportError(
                    "httpx is required for HttpTransport; "
                    "pip install 'computelayer[http]'"
                ) from exc
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "computelayer-python/0.1.0",
                },
            )
        return self._client

    def _with_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.project and "project" not in payload and "project_id" not in payload:
            return {**payload, "project": self.project}
        return payload

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        client = self._ensure_client()
        try:
            response = await client.request(method, path, json=payload)
        except Exception as exc:  # httpx transport-level failures
            raise TransportError(f"{method} {path} failed: {exc}") from exc

        if response.status_code >= 400:
            try:
                body = response.json()
                message = body.get("detail") or body.get("message") or response.text
            except Exception:
                body, message = None, response.text
            raise APIError(response.status_code, str(message), body)

        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    # -- endpoints --------------------------------------------------------

    async def lookup(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", "/computations/lookup", self._with_project(payload)
        )

    async def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", "/computations/start", self._with_project(payload)
        )

    async def complete(
        self, computation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST", f"/computations/{computation_id}/complete", payload
        )

    async def fail(self, computation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", f"/computations/{computation_id}/fail", payload
        )

    async def upsert_resource(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", "/resources/upsert", self._with_project(payload)
        )

    async def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/runs", self._with_project(payload))

    async def finish_run(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/runs/{run_id}/finish", payload)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/runs/{run_id}")

    async def get_run_graph(self, run_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/runs/{run_id}/graph")

    async def get_metrics(self, period: str = "30d") -> dict[str, Any]:
        project = self.project or ""
        return await self._request("GET", f"/projects/{project}/metrics?period={period}")

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None
