"""Model-switch preview endpoint (V0.2, spec section 4)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_portable_artifact_is_marked_reusable(cl, http_client) -> None:
    async with cl.run() as run:
        await cl.compute.run(
            name="fact_extraction",
            inputs={"ticker": "NVDA"},
            model="openai/gpt-4o",
            artifact_type="fact",
            fn=lambda: {"revenue": 100},
        )

    response = await http_client.post(
        f"/runs/{run.id}/preview-model-switch",
        json={"target_model": "anthropic/claude-3-5-sonnet"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["reusable_count"] == 1
    assert body["recompute_count"] == 0
    assert body["estimated_incremental_cost_usd"] == 0.0
    item = body["items"][0]
    assert item["name"] == "fact_extraction"
    assert item["decision"] == "REUSE"
    assert item["current_model"] == "openai/gpt-4o"
    assert "claude" in item["reason"]


@pytest.mark.asyncio
async def test_unclassified_computation_needs_recompute(cl, http_client) -> None:
    async with cl.run() as run:
        await cl.compute.run(
            name="untyped_step",
            inputs={"ticker": "NVDA"},
            model="openai/gpt-4o",
            # No artifact_type -- never eligible as a cross-model source.
            fn=lambda: {"a": 1},
        )

    response = await http_client.post(
        f"/runs/{run.id}/preview-model-switch",
        json={"target_model": "anthropic/claude-3-5-sonnet"},
    )
    body = response.json()

    assert body["reusable_count"] == 0
    assert body["recompute_count"] == 1
    item = body["items"][0]
    assert item["decision"] == "RECOMPUTE"
    assert "artifact_type" in item["reason"]


@pytest.mark.asyncio
async def test_policy_override_flips_the_preview(cl, http_client) -> None:
    async with cl.run() as run:
        await cl.compute.run(
            name="draft_writing",
            inputs={"ticker": "NVDA"},
            model="openai/gpt-4o",
            artifact_type="draft",
            fn=lambda: {"text": "..."},
        )

    # Portable by default -> REUSE.
    before = await http_client.post(
        f"/runs/{run.id}/preview-model-switch",
        json={"target_model": "anthropic/claude-3-5-sonnet"},
    )
    assert before.json()["items"][0]["decision"] == "REUSE"

    await http_client.put(
        "/artifact-policies/draft", json={"portable": False, "scope": "workspace"}
    )

    after = await http_client.post(
        f"/runs/{run.id}/preview-model-switch",
        json={"target_model": "anthropic/claude-3-5-sonnet"},
    )
    item = after.json()["items"][0]
    assert item["decision"] == "RECOMPUTE"
    assert "not portable" in item["reason"]


@pytest.mark.asyncio
async def test_estimated_incremental_cost_sums_recompute_only(cl, http_client) -> None:
    async with cl.run() as run:
        await cl.compute.run(
            name="reusable_fact",
            inputs={"ticker": "NVDA"},
            model="openai/gpt-4o",
            artifact_type="fact",
            fn=lambda: {"a": 1},
        )
        # No artifact_type: always RECOMPUTE, and its cost should count toward
        # the estimate even though the reusable item's shouldn't.
        completed = await cl.compute.run(
            name="final_write",
            inputs={"ticker": "NVDA"},
            model="openai/gpt-4o",
            fn=lambda: {"draft": "..."},
        )

    # Give the second computation a nonzero recorded cost directly, since the
    # local test fn doesn't report LLM usage.
    await http_client.post(
        f"/computations/{completed.computation_id}/complete",
        json={"output_json": {"draft": "..."}, "output_hash": "b" * 64, "cost_usd": 0.42},
    )

    response = await http_client.post(
        f"/runs/{run.id}/preview-model-switch",
        json={"target_model": "anthropic/claude-3-5-sonnet"},
    )
    body = response.json()
    assert body["reusable_count"] == 1
    assert body["recompute_count"] == 1
    assert body["estimated_incremental_cost_usd"] == pytest.approx(0.42)
