"""Live test: real OpenRouter LLM calls through computelayer.openai, run
three times to prove the core claim end to end with a real model and real
dollars -- not the benchmark's deterministic fixtures (fake_llm.py).

Setup:
    export OPENROUTER_API_KEY=sk-or-...
    export COMPUTELAYER_API_URL=https://api-production-f1122.up.railway.app/v1
    export COMPUTELAYER_API_KEY=cl_live_...          # your provisioned key
    export COMPUTELAYER_PROJECT=research-agent

Run:
    python examples/openrouter_live_test.py

What it proves, in order:
    pass 1 (cold)              -- real OpenRouter call, real cost recorded
    pass 2 (identical rerun)   -- HIT: no OpenRouter call happens at all
    pass 3 (different topic)   -- MISS again: a genuinely new question
"""

from __future__ import annotations

import asyncio
import os

from computelayer import ComputeLayer
from computelayer.openai import OpenAI
from computelayer.transport import HttpTransport

# In MODEL_PRICING (packages/python-sdk/computelayer/pricing.py) as a
# fallback, but OpenRouter's own usage.cost -- requested via
# usage={"include": True} below -- wins when present (spec §26).
MODEL = "meta-llama/llama-3.1-70b-instruct"


def client() -> ComputeLayer:
    project = os.environ["COMPUTELAYER_PROJECT"]
    return ComputeLayer(
        project=project,
        transport=HttpTransport(
            api_key=os.environ["COMPUTELAYER_API_KEY"],
            base_url=os.environ["COMPUTELAYER_API_URL"],
            project=project,
        ),
    )


async def summarize(topic: str) -> str:
    llm = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )
    response = await llm.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": f"In exactly one sentence, what is {topic}?"}],
        usage={"include": True},
    )
    await llm.aclose()
    return response["choices"][0]["message"]["content"]


async def pass_(label: str, external_id: str, topic: str) -> None:
    cl = client()
    async with cl.run(external_run_id=external_id) as run:
        result = await cl.compute.run(
            name="summarize_topic",
            inputs={"topic": topic},
            fn=lambda: summarize(topic),
        )
    print(f"\n[{label}]  run_id={run.id}")
    print(f"  cache_status = {result.cache_status}")
    print(f"  value        = {result.value}")
    print(
        f"  cost=${result.cost_usd:.5f}  saved=${result.saved_usd:.5f}  "
        f"tokens_in={result.input_tokens}  tokens_out={result.output_tokens}  "
        f"latency={result.latency_ms}ms"
    )
    await cl.aclose()


async def main() -> None:
    for var in ("OPENROUTER_API_KEY", "COMPUTELAYER_API_URL", "COMPUTELAYER_API_KEY"):
        if not os.getenv(var):
            raise SystemExit(f"missing required env var: {var}")

    await pass_("PASS 1 — cold, real OpenRouter call", "openrouter-live-1-cold", "incremental compute")
    await pass_(
        "PASS 2 — identical rerun, should be a HIT with zero OpenRouter calls",
        "openrouter-live-2-identical",
        "incremental compute",
    )
    await pass_(
        "PASS 3 — different topic, a genuinely new MISS",
        "openrouter-live-3-different-topic",
        "deterministic caching",
    )


if __name__ == "__main__":
    asyncio.run(main())
