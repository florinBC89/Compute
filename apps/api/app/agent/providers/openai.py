"""Real OpenAI calls for the research pipeline (V0.2 human workspace, Phase 4).

Uses the real `openai` package -- not the SDK's hand-rolled httpx client at
`computelayer.openai`, which exists specifically to keep the SDK *core*
dependency-free (packages/python-sdk/pyproject.toml has zero required
deps). apps/api already carries fastapi/sqlalchemy/etc., so that
constraint doesn't apply here, and a maintained provider SDK is safer than
hand-rolling another HTTP client for a real consumer product.

Every call records usage via `record_llm_call()` with the same
usage-extraction shape `computelayer.openai`'s `_record()` uses, so
`Compute.run()`'s existing `_resolve_cost()` picks it up automatically --
zero changes to the reuse/cost-ledger engine to attribute real spend.
"""

from __future__ import annotations

import time

from computelayer.context import LLMCall, record_llm_call
from computelayer.pricing import estimate_cost
from openai import AsyncOpenAI

from app.config import get_settings

#: The pricing-table key (see computelayer.pricing.MODEL_PRICING) --
#: intentionally distinct from the real API model id below, matching the
#: "provider/model" convention every other model string in this codebase
#: already uses (openai/gpt-4o, anthropic/claude-sonnet-4, ...).
MODEL = "openai/gpt-4o-mini"
_REAL_MODEL = "gpt-4o-mini"

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def complete(*, system: str, prompt: str, max_tokens: int = 400) -> str:
    client = _get_client()
    started = time.perf_counter()
    response = await client.chat.completions.create(
        model=_REAL_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    cost_usd = estimate_cost(MODEL, input_tokens, output_tokens)

    record_llm_call(
        LLMCall(
            model=MODEL,
            provider="openai",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
    )

    return (response.choices[0].message.content or "").strip()
