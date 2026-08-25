"""Direct endpoint checks (spec §29-§36)."""

from __future__ import annotations

import pytest

from computelayer import build_fingerprint, build_logical_key


def _keys(name: str, inputs: dict) -> dict:
    return {
        "name": name,
        "logical_key": build_logical_key(name=name, inputs=inputs),
        "fingerprint": build_fingerprint(name=name, inputs=inputs),
    }


@pytest.mark.asyncio
async def test_health(http_client) -> None:
    response = await http_client.get("http://testserver/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_unauthenticated_requests_are_rejected(http_client) -> None:
    response = await http_client.post(
        "/computations/lookup",
        json={**_keys("x", {"a": 1}), "force": False},
        headers={"Authorization": ""},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_lookup_start_complete_cycle(http_client) -> None:
    keys = _keys("financials", {"ticker": "NVDA"})

    miss = await http_client.post("/computations/lookup", json=keys)
    assert miss.json()["status"] == "MISS"

    started = await http_client.post(
        "/computations/start", json={**keys, "input_json": {"ticker": "NVDA"}}
    )
    computation_id = started.json()["computation_id"]

    completed = await http_client.post(
        f"/computations/{computation_id}/complete",
        json={
            "output_json": {"revenue": 100},
            "output_hash": "a" * 64,
            "input_tokens": 10,
            "output_tokens": 5,
            "cost_usd": 0.25,
            "latency_ms": 1200,
        },
    )
    assert completed.json()["status"] == "SUCCEEDED"

    hit = await http_client.post("/computations/lookup", json=keys)
    body = hit.json()
    assert body["status"] == "HIT"
    assert body["computation"]["output"] == {"revenue": 100}
    assert body["computation"]["cost_usd"] == 0.25


@pytest.mark.asyncio
async def test_failed_computation_is_never_reused(http_client) -> None:
    keys = _keys("flaky", {"ticker": "NVDA"})

    started = await http_client.post("/computations/start", json=keys)
    computation_id = started.json()["computation_id"]
    await http_client.post(
        f"/computations/{computation_id}/fail",
        json={"error_type": "TimeoutError", "error_message": "provider timed out"},
    )

    again = await http_client.post("/computations/lookup", json=keys)
    assert again.json()["status"] == "MISS"


@pytest.mark.asyncio
async def test_resource_upsert_reports_change(http_client) -> None:
    first = await http_client.post(
        "/resources/upsert",
        json={"resource_key": "company:NVDA:financials", "version": "sha256:abc"},
    )
    assert first.json() == {
        "changed": True,
        "previous_version": None,
        "current_version": "sha256:abc",
    }

    second = await http_client.post(
        "/resources/upsert",
        json={"resource_key": "company:NVDA:financials", "version": "sha256:abc"},
    )
    assert second.json()["changed"] is False

    third = await http_client.post(
        "/resources/upsert",
        json={"resource_key": "company:NVDA:financials", "version": "sha256:def"},
    )
    assert third.json()["previous_version"] == "sha256:abc"


@pytest.mark.asyncio
async def test_run_summary_and_graph(cl, http_client) -> None:
    async with cl.run() as run:
        upstream = await cl.compute.run(
            name="financials", inputs={"ticker": "NVDA"}, fn=lambda: {"revenue": 1}
        )
        await cl.compute.run(
            name="analysis", inputs={"financials": upstream}, fn=lambda: {"v": "buy"}
        )
        await cl.compute.run(
            name="financials", inputs={"ticker": "NVDA"}, fn=lambda: {"revenue": 1}
        )

    summary = run.summary
    assert summary["computations"] == 3
    assert summary["hits"] == 1
    assert summary["misses"] == 2

    graph = await cl.get_run_graph(run.id)
    assert len(graph["nodes"]) == 3
    assert any(edge["from"] == upstream.computation_id for edge in graph["edges"])

    listing = (await http_client.get("/runs")).json()["runs"]
    assert listing[0]["id"] == run.id
    assert listing[0]["computations"] == 3
    assert listing[0]["hits"] == 1


@pytest.mark.asyncio
async def test_duplicate_dependency_keys_are_rejected(http_client) -> None:
    keys = _keys("dup", {"a": 1})
    response = await http_client.post(
        "/computations/start",
        json={
            **keys,
            "dependencies": [
                {"key": "k", "version": "v1", "type": "EXTERNAL"},
                {"key": "k", "version": "v2", "type": "EXTERNAL"},
            ],
        },
    )
    assert response.status_code == 400
