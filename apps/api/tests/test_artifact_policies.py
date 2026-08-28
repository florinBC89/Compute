"""Cross-model reuse portability policy endpoints (V0.2)."""

from __future__ import annotations

import pytest

from computelayer import build_fingerprint, build_logical_key, build_model_agnostic_fingerprint


def _keys(name: str, inputs: dict, model: str) -> dict:
    return {
        "name": name,
        "logical_key": build_logical_key(name=name, inputs=inputs),
        "fingerprint": build_fingerprint(name=name, inputs=inputs, model=model),
        "model_agnostic_fingerprint": build_model_agnostic_fingerprint(
            name=name, inputs=inputs
        ),
    }


@pytest.mark.asyncio
async def test_defaults_before_any_policy_row_exists(http_client) -> None:
    response = await http_client.get("/artifact-policies")
    assert response.status_code == 200
    policies = {p["artifact_type"]: p for p in response.json()["policies"]}

    assert set(policies) == {
        "source",
        "fact",
        "structured_data",
        "research_note",
        "analysis",
        "draft",
        "citation",
    }
    # DEFAULT_PORTABLE_ARTIFACT_TYPES treats every type as portable until a
    # policy row overrides it.
    assert all(p["portable"] is True for p in policies.values())
    assert all(p["source"] == "default" for p in policies.values())


@pytest.mark.asyncio
async def test_workspace_default_can_be_overridden(http_client) -> None:
    updated = await http_client.put(
        "/artifact-policies/draft", json={"portable": False, "scope": "workspace"}
    )
    assert updated.status_code == 200
    policies = {p["artifact_type"]: p for p in updated.json()["policies"]}
    assert policies["draft"] == {
        "artifact_type": "draft",
        "portable": False,
        "source": "workspace",
    }
    # Untouched types keep falling back to the hardcoded default.
    assert policies["source"]["source"] == "default"


@pytest.mark.asyncio
async def test_project_override_wins_over_workspace_default(http_client) -> None:
    await http_client.put(
        "/artifact-policies/fact", json={"portable": False, "scope": "workspace"}
    )
    await http_client.put(
        "/artifact-policies/fact", json={"portable": True, "scope": "project"}
    )

    listing = (await http_client.get("/artifact-policies")).json()["policies"]
    fact = next(p for p in listing if p["artifact_type"] == "fact")
    assert fact == {"artifact_type": "fact", "portable": True, "source": "project"}


@pytest.mark.asyncio
async def test_setting_a_type_non_portable_blocks_cross_model_reuse(http_client) -> None:
    # Same shape as the SDK's cross_model_reuse conformance scenario, but
    # this time exercising the DB-backed policy path (not just the
    # hardcoded fallback): flipping "fact" to non-portable must make an
    # otherwise-eligible model switch resolve to STALE, not HIT.
    await http_client.put(
        "/artifact-policies/fact", json={"portable": False, "scope": "workspace"}
    )

    first_keys = _keys("fact_extraction", {"ticker": "NVDA"}, "openai/gpt-4o")
    await http_client.post("/computations/lookup", json={**first_keys, "artifact_type": "fact"})
    started = await http_client.post(
        "/computations/start", json={**first_keys, "artifact_type": "fact"}
    )
    await http_client.post(
        f"/computations/{started.json()['computation_id']}/complete",
        json={"output_json": {"revenue": 100}, "output_hash": "a" * 64},
    )

    second_keys = _keys("fact_extraction", {"ticker": "NVDA"}, "anthropic/claude-3-5-sonnet")
    second_lookup = await http_client.post(
        "/computations/lookup",
        json={
            **second_keys,
            "artifact_type": "fact",
            "cross_model_reuse": True,
        },
    )
    body = second_lookup.json()
    assert body["status"] == "STALE"
    assert body["reuse_kind"] is None
