"""OpenAI-compatible LLM instrumentation (spec §25).

The LLM request itself is not cached.  What gets cached is the *surrounding
computation* -- so when that computation is reused, the request never happens.
This wrapper's only job is to attribute tokens, latency and cost to whichever
``compute.run`` body is currently executing.

Two ways in::

    from computelayer.openai import OpenAI
    client = OpenAI(api_key=..., base_url="https://openrouter.ai/api/v1")

or wrap a client you already have::

    from computelayer.openai import instrument
    client = instrument(openai.AsyncOpenAI())
"""

from __future__ import annotations

import time
from typing import Any

from computelayer.context import LLMCall, record_llm_call
from computelayer.errors import TransportError
from computelayer.pricing import estimate_cost

__all__ = ["AsyncOpenAI", "OpenAI", "instrument"]

DEFAULT_BASE_URL = "https://api.openai.com/v1"


def _usage_from(payload: dict[str, Any]) -> tuple[int, int]:
    usage = payload.get("usage") or {}
    return (
        int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
        int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
    )


def _provider_cost(payload: dict[str, Any]) -> float | None:
    """OpenRouter reports ``usage.cost``; most providers report nothing."""
    usage = payload.get("usage") or {}
    for key in ("cost", "total_cost", "cost_usd"):
        if usage.get(key) is not None:
            return float(usage[key])
    return None


def _record(
    payload: dict[str, Any], *, requested_model: str, began: float, provider: str | None
) -> None:
    input_tokens, output_tokens = _usage_from(payload)
    model = payload.get("model") or requested_model
    reported = _provider_cost(payload)
    record_llm_call(
        LLMCall(
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_cost(
                model, input_tokens, output_tokens, provider_reported_cost=reported
            ),
            latency_ms=int((time.monotonic() - began) * 1000),
            metadata={
                "id": payload.get("id"),
                "cost_source": "provider" if reported is not None else "local_pricing",
            },
        )
    )


# --------------------------------------------------------------------------
# wrapping an existing OpenAI SDK client
# --------------------------------------------------------------------------


def instrument(client: Any, *, provider: str | None = None) -> Any:
    """Patch ``client.chat.completions.create`` to record usage.

    Works with both the sync and async official OpenAI clients, and with
    anything else exposing the same shape.
    """
    completions = client.chat.completions
    original = completions.create

    if getattr(original, "__computelayer_instrumented__", False):
        return client

    import inspect

    if inspect.iscoroutinefunction(original):

        async def create(*args: Any, **kwargs: Any) -> Any:
            began = time.monotonic()
            response = await original(*args, **kwargs)
            _record(
                _as_dict(response),
                requested_model=kwargs.get("model", ""),
                began=began,
                provider=provider,
            )
            return response

    else:

        def create(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
            began = time.monotonic()
            response = original(*args, **kwargs)
            _record(
                _as_dict(response),
                requested_model=kwargs.get("model", ""),
                began=began,
                provider=provider,
            )
            return response

    create.__computelayer_instrumented__ = True  # type: ignore[attr-defined]
    completions.create = create  # type: ignore[assignment]
    return client


def _as_dict(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    for attr in ("model_dump", "dict", "to_dict"):
        method = getattr(response, attr, None)
        if callable(method):
            try:
                return method()
            except Exception:  # pragma: no cover - defensive
                continue
    return {}


# --------------------------------------------------------------------------
# a minimal built-in client (no `openai` package required)
# --------------------------------------------------------------------------


class _Completions:
    def __init__(self, owner: "AsyncOpenAI") -> None:
        self._owner = owner

    async def create(self, **kwargs: Any) -> dict[str, Any]:
        began = time.monotonic()
        payload = await self._owner._post("/chat/completions", kwargs)
        _record(
            payload,
            requested_model=kwargs.get("model", ""),
            began=began,
            provider=self._owner.provider,
        )
        return payload


class _Chat:
    def __init__(self, owner: "AsyncOpenAI") -> None:
        self.completions = _Completions(owner)


class AsyncOpenAI:
    """A small OpenAI-compatible async client with usage recording built in."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        provider: str | None = None,
        timeout: float = 120.0,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.provider = provider or _provider_from_url(base_url)
        self.timeout = timeout
        self.default_headers = default_headers or {}
        self._client: Any = None
        self.chat = _Chat(self)

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                import httpx
            except ImportError as exc:  # pragma: no cover - import guard
                raise TransportError(
                    "httpx is required for computelayer.openai; "
                    "pip install 'computelayer[http]'"
                ) from exc
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    **self.default_headers,
                },
            )
        return self._client

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        client = self._ensure_client()
        response = await client.post(path, json=body)
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


#: Alias kept because the spec writes ``from computelayer.openai import OpenAI``.
OpenAI = AsyncOpenAI


def _provider_from_url(base_url: str) -> str:
    if "openrouter" in base_url:
        return "openrouter"
    if "anthropic" in base_url:
        return "anthropic"
    if "openai" in base_url:
        return "openai"
    return "openai-compatible"
