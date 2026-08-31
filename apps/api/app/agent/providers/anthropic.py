"""Real Anthropic calls for the research pipeline (V0.2 human workspace,
Phase 7).

Same shape as providers/openai.py: a maintained provider SDK (apps/api
already carries fastapi/sqlalchemy, so the SDK core's dependency-free
constraint doesn't apply here), real usage recorded via record_llm_call()
so Compute.run()'s cost ledger picks it up automatically.
"""

from __future__ import annotations

import time
from typing import Awaitable, Callable

from anthropic import AsyncAnthropic
from computelayer.context import LLMCall, record_llm_call
from computelayer.pricing import estimate_cost

from app.config import get_settings

#: claude-haiku-4-5 -- Anthropic's fastest/cheapest current-generation
#: model, the same cost tier as openai/gpt-4o-mini (see providers/openai.py)
#: so switching providers doesn't also silently change the cost tier.
MODEL = "anthropic/claude-haiku-4-5"
_REAL_MODEL = "claude-haiku-4-5"

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def complete(*, system: str, prompt: str, max_tokens: int = 400) -> str:
    client = _get_client()
    started = time.perf_counter()
    response = await client.messages.create(
        model=_REAL_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = estimate_cost(MODEL, input_tokens, output_tokens)

    record_llm_call(
        LLMCall(
            model=MODEL,
            provider="anthropic",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    return text.strip()


async def stream_complete(
    *,
    system: str,
    history: list[dict[str, str]],
    message: str,
    max_tokens: int = 400,
    on_delta: Callable[[str], Awaitable[None]],
) -> str:
    client = _get_client()
    started = time.perf_counter()

    messages: list[dict[str, object]] = [
        {"role": turn["role"], "content": turn["content"]} for turn in history
    ]
    messages.append({"role": "user", "content": message})

    if history:
        last_history_content = messages[len(history) - 1]["content"]
        messages[len(history) - 1]["content"] = [
            {
                "type": "text",
                "text": last_history_content,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    full_text = ""
    input_tokens = 0
    output_tokens = 0
    async with client.messages.stream(
        model=_REAL_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    ) as stream:
        async for event in stream:
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                full_text += event.delta.text
                await on_delta(event.delta.text)
            elif event.type == "message_start":
                input_tokens = event.message.usage.input_tokens
            elif event.type == "message_delta":
                output_tokens = event.usage.output_tokens

    latency_ms = int((time.perf_counter() - started) * 1000)
    cost_usd = estimate_cost(MODEL, input_tokens, output_tokens)

    record_llm_call(
        LLMCall(
            model=MODEL,
            provider="anthropic",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
    )

    return full_text.strip()
