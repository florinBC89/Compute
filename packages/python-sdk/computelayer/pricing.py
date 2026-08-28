"""Cost tracking (spec §26).

Provider-reported cost is preferred when available; local pricing is the
fallback.  Pricing can be overridden without touching code by pointing
``COMPUTELAYER_PRICING_FILE`` at a JSON file of the same shape as
:data:`MODEL_PRICING`.
"""

from __future__ import annotations

import json
import os
from typing import Any

__all__ = ["MODEL_PRICING", "estimate_cost", "load_pricing", "register_model_pricing"]

PRICING_FILE_ENV = "COMPUTELAYER_PRICING_FILE"

#: ``provider/model`` -> USD per million tokens.  Indicative defaults only;
#: override them for your account's real rates.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "openai/gpt-4o": {"input_per_million": 2.50, "output_per_million": 10.00},
    "openai/gpt-4o-mini": {"input_per_million": 0.15, "output_per_million": 0.60},
    "anthropic/claude-sonnet-5": {
        "input_per_million": 2.00,
        "output_per_million": 10.00,
    },
    "anthropic/claude-haiku-4-5": {
        "input_per_million": 1.00,
        "output_per_million": 5.00,
    },
    # gemini-2.5-flash is retired (confirmed live against the real API,
    # 2026-08-28); gemini-3.6-flash is its current fast/cheap-tier
    # successor.
    "google/gemini-3.6-flash": {
        "input_per_million": 0.30,
        "output_per_million": 2.50,
    },
    "meta-llama/llama-3.1-70b-instruct": {
        "input_per_million": 0.30,
        "output_per_million": 0.30,
    },
    # Used by the deterministic benchmark fixtures.
    "benchmark/deterministic": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    },
}

_loaded_from_file = False


def load_pricing(path: str | None = None) -> dict[str, dict[str, float]]:
    """Merge a pricing JSON file into :data:`MODEL_PRICING` (idempotent)."""
    global _loaded_from_file
    path = path or os.getenv(PRICING_FILE_ENV)
    if not path:
        return MODEL_PRICING
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data: dict[str, Any] = json.load(handle)
    except FileNotFoundError:
        return MODEL_PRICING
    for model, prices in data.items():
        MODEL_PRICING[model] = {
            "input_per_million": float(prices["input_per_million"]),
            "output_per_million": float(prices["output_per_million"]),
        }
    _loaded_from_file = True
    return MODEL_PRICING


def register_model_pricing(
    model: str, *, input_per_million: float, output_per_million: float
) -> None:
    MODEL_PRICING[model] = {
        "input_per_million": float(input_per_million),
        "output_per_million": float(output_per_million),
    }


def estimate_cost(
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    *,
    provider_reported_cost: float | None = None,
) -> float:
    """Cost in USD for one LLM call.

    Provider-reported cost wins when present (§26); otherwise the local table
    is used.  An unknown model yields ``0.0`` rather than an exception -- a
    missing price should not abort an agent run, it should show up as an
    obviously-zero cost in the dashboard.
    """
    if provider_reported_cost is not None:
        return float(provider_reported_cost)

    if not _loaded_from_file:
        load_pricing()

    if not model:
        return 0.0

    prices = MODEL_PRICING.get(model)
    if prices is None and "/" in model:
        # Accept "openrouter/openai/gpt-4o" and similar prefixed forms.
        suffix = model.split("/", 1)[1]
        prices = MODEL_PRICING.get(suffix)
    if prices is None:
        return 0.0

    return (
        input_tokens * prices["input_per_million"]
        + output_tokens * prices["output_per_million"]
    ) / 1_000_000
