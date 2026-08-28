"""Real Gemini calls for the research pipeline (V0.2 human workspace,
Phase 7).

Same shape as providers/openai.py and providers/anthropic.py. `MODEL` is
`gemini-3.6-flash`, not the more commonly-referenced `gemini-2.5-flash` --
confirmed live against the real API (2026-08-28) that 2.5-flash has been
retired ("no longer available to new users"); 3.6-flash is its current
fast/cheap-tier successor.
"""

from __future__ import annotations

import time

from computelayer.context import LLMCall, record_llm_call
from computelayer.pricing import estimate_cost
from google import genai
from google.genai import types

from app.config import get_settings

MODEL = "google/gemini-3.6-flash"
_REAL_MODEL = "gemini-3.6-flash"

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


async def complete(*, system: str, prompt: str, max_tokens: int = 400) -> str:
    client = _get_client()
    started = time.perf_counter()
    response = await client.aio.models.generate_content(
        model=_REAL_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system, max_output_tokens=max_tokens
        ),
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0
    cost_usd = estimate_cost(MODEL, input_tokens, output_tokens)

    record_llm_call(
        LLMCall(
            model=MODEL,
            provider="google",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
    )

    return (response.text or "").strip()
