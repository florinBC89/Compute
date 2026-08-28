"""Project metrics, artifacts and usage endpoints (spec §36, V0.2)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_cross_model_saved_usd_is_a_subset_of_saved_usd(cl, http_client) -> None:
    first = await cl.compute.run(
        name="fact_extraction",
        inputs={"ticker": "NVDA"},
        model="openai/gpt-4o",
        artifact_type="fact",
        fn=lambda: {"revenue": 100},
    )
    await http_client.post(
        f"/computations/{first.computation_id}/complete",
        json={"output_json": {"revenue": 100}, "output_hash": "a" * 64, "cost_usd": 0.50},
    )

    second = await cl.compute.run(
        name="fact_extraction",
        inputs={"ticker": "NVDA"},
        model="anthropic/claude-3-5-sonnet",
        artifact_type="fact",
        cross_model_reuse=True,
        fn=lambda: {"revenue": 100},
    )
    assert second.reuse_kind == "CROSS_MODEL"

    metrics = (await http_client.get("/projects/conformance/metrics")).json()
    assert metrics["saved_usd"] == pytest.approx(0.50)
    assert metrics["cross_model_saved_usd"] == pytest.approx(0.50)


@pytest.mark.asyncio
async def test_same_model_hit_does_not_count_as_cross_model(cl, http_client) -> None:
    first = await cl.compute.run(
        name="financials",
        inputs={"ticker": "NVDA"},
        fn=lambda: {"revenue": 1},
    )
    await http_client.post(
        f"/computations/{first.computation_id}/complete",
        json={"output_json": {"revenue": 1}, "output_hash": "c" * 64, "cost_usd": 0.10},
    )
    await cl.compute.run(name="financials", inputs={"ticker": "NVDA"}, fn=lambda: {"revenue": 1})

    metrics = (await http_client.get("/projects/conformance/metrics")).json()
    assert metrics["saved_usd"] == pytest.approx(0.10)
    assert metrics["cross_model_saved_usd"] == 0.0


@pytest.mark.asyncio
async def test_artifacts_lists_newest_row_per_logical_key(cl, http_client) -> None:
    await cl.compute.run(
        name="fact_extraction",
        inputs={"ticker": "NVDA"},
        dependencies=[cl.dep("financials:NVDA", version="v1")],
        model="openai/gpt-4o",
        artifact_type="fact",
        fn=lambda: {"revenue": 100},
    )
    # A second, distinct logical key with a different artifact_type.
    await cl.compute.run(
        name="draft_writing",
        inputs={"ticker": "NVDA"},
        model="openai/gpt-4o",
        artifact_type="draft",
        fn=lambda: {"text": "..."},
    )
    # An unclassified computation must not appear.
    await cl.compute.run(
        name="untyped_step", inputs={"ticker": "NVDA"}, fn=lambda: {"a": 1}
    )

    listing = (await http_client.get("/projects/conformance/artifacts")).json()
    names = {a["name"] for a in listing["artifacts"]}
    assert names == {"fact_extraction", "draft_writing"}

    filtered = (
        await http_client.get("/projects/conformance/artifacts?artifact_type=fact")
    ).json()
    assert [a["name"] for a in filtered["artifacts"]] == ["fact_extraction"]


@pytest.mark.asyncio
async def test_usage_breaks_down_by_model_and_excludes_hits(cl, http_client) -> None:
    a = await cl.compute.run(
        name="financials", inputs={"ticker": "NVDA"}, model="openai/gpt-4o",
        fn=lambda: {"revenue": 1},
    )
    await http_client.post(
        f"/computations/{a.computation_id}/complete",
        json={"output_json": {"revenue": 1}, "output_hash": "d" * 64, "cost_usd": 0.30, "model": "openai/gpt-4o"},
    )
    # A same-model re-run: a HIT, must not inflate usage totals.
    await cl.compute.run(name="financials", inputs={"ticker": "NVDA"}, model="openai/gpt-4o", fn=lambda: {"revenue": 1})

    usage = (await http_client.get("/projects/conformance/usage")).json()
    items = {(item["model"], item["name"]): item for item in usage["items"]}
    entry = items[("openai/gpt-4o", "financials")]
    assert entry["computations"] == 1
    assert entry["cost_usd"] == pytest.approx(0.30)
