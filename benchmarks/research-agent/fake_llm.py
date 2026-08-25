"""A deterministic stand-in for an LLM provider.

The benchmark measures *reuse*, not model quality, so the model is replaced by
a function that is deterministic in its inputs and reports plausible token
counts. This keeps the whole benchmark runnable with no provider key and makes
every number reproducible across machines.

It records usage through :func:`computelayer.record_llm_call`, exactly as the
real ``computelayer.openai`` wrapper does, so cost and token accounting take
the same code path they would in production.

Latency is *modelled*, not measured: a real call to a frontier model takes
seconds, and sleeping through that would make the benchmark useless as a
development tool. Every latency figure in the report is labelled accordingly.
"""

from __future__ import annotations

import hashlib
from typing import Any

from computelayer import LLMCall, canonical_json, record_llm_call
from computelayer.pricing import estimate_cost

MODEL = "benchmark/deterministic"

#: Modelled provider latency: a fixed handshake plus per-output-token decoding.
_BASE_LATENCY_MS = 380
_MS_PER_OUTPUT_TOKEN = 11

#: Roughly four characters per token, the usual English approximation.
_CHARS_PER_TOKEN = 4

#: Modelled latency of one fixture fetch, standing in for an API round trip.
TOOL_LATENCY_MS = 240


def _digest(*parts: Any) -> str:
    return hashlib.sha256(canonical_json(list(parts)).encode("utf-8")).hexdigest()


def _output_tokens(seed: str) -> int:
    """Deterministic 320-1200 tokens, the range a section of prose occupies."""
    return 320 + int(seed[:8], 16) % 880


class DeterministicLLM:
    """Callable stand-in with the accounting surface of a real client."""

    def __init__(self, model: str = MODEL) -> None:
        self.model = model
        self.calls = 0
        #: Modelled latency per step, so the report can total it. Wall-clock
        #: latency here is ~0 and would be meaningless.
        self.latency_by_task: dict[str, int] = {}

    async def complete(self, *, prompt: str, context: Any, task: str) -> dict[str, Any]:
        seed = _digest(prompt, context, task)

        serialized = canonical_json(context)
        input_tokens = len(prompt) // _CHARS_PER_TOKEN + len(serialized) // _CHARS_PER_TOKEN
        output_tokens = _output_tokens(seed)
        latency_ms = _BASE_LATENCY_MS + output_tokens * _MS_PER_OUTPUT_TOKEN

        record_llm_call(
            LLMCall(
                model=self.model,
                provider="benchmark",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=estimate_cost(self.model, input_tokens, output_tokens),
                latency_ms=latency_ms,
                metadata={"task": task, "modelled_latency": True},
            )
        )
        self.calls += 1
        self.latency_by_task[task] = latency_ms

        # The text is deterministic in the inputs, which is what matters: if the
        # inputs did not change, neither does the output hash, and downstream
        # computations stay reusable.
        return {
            "task": task,
            "summary": f"{task} for the supplied context",
            "digest": seed[:16],
            "detail": _paragraphs(seed, output_tokens),
        }


def _paragraphs(seed: str, output_tokens: int) -> list[str]:
    """Deterministic filler standing in for generated prose."""
    sentences = max(1, output_tokens // 160)
    return [f"Observation {index + 1} ({seed[index * 2 : index * 2 + 6]})."
            for index in range(sentences)]
