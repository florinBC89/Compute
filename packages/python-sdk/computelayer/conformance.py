"""Backend conformance suite.

Each scenario is a sequence of ``compute.run`` calls plus the exact
cache-status trace a correct backend must produce.  The suite runs against any
:class:`~computelayer.client.ComputeLayer` instance, so the in-memory reference
backend and the PostgreSQL API are held to one standard:

* ``packages/python-sdk/tests/test_conformance.py`` runs it against
  ``LocalBackend``.
* ``apps/api/tests/test_conformance.py`` runs it against the real API.

If the two ever disagree, one of them is reusing something it should not --
the failure mode §61 calls unacceptable -- and the suite fails loudly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from computelayer.client import ComputeLayer

__all__ = ["Scenario", "SCENARIOS", "run_scenario", "run_all"]


@dataclass
class Trace:
    statuses: list[str] = field(default_factory=list)
    executions: int = 0
    values: list[Any] = field(default_factory=list)

    def as_tuple(self) -> tuple[tuple[str, ...], int]:
        return tuple(self.statuses), self.executions


@dataclass
class Scenario:
    name: str
    description: str
    body: Callable[[ComputeLayer, Trace], Awaitable[None]]
    expected_statuses: tuple[str, ...]
    expected_executions: int


async def run_scenario(scenario: Scenario, client: ComputeLayer) -> Trace:
    trace = Trace()
    await scenario.body(client, trace)
    return trace


async def run_all(
    client_factory: Callable[[], ComputeLayer]
) -> dict[str, tuple[Trace, bool]]:
    """Run every scenario against a fresh client; report pass/fail per scenario."""
    results: dict[str, tuple[Trace, bool]] = {}
    for scenario in SCENARIOS:
        client = client_factory()
        trace = await run_scenario(scenario, client)
        ok = (
            tuple(trace.statuses) == scenario.expected_statuses
            and trace.executions == scenario.expected_executions
        )
        results[scenario.name] = (trace, ok)
        await client.aclose()
    return results


# --------------------------------------------------------------------------
# scenarios
# --------------------------------------------------------------------------


def _counting(trace: Trace, value: Any) -> Callable[[], Any]:
    def body() -> Any:
        trace.executions += 1
        return value

    return body


async def _identical_rerun(cl: ComputeLayer, trace: Trace) -> None:
    for _ in range(3):
        result = await cl.compute.run(
            name="financials",
            inputs={"ticker": "NVDA"},
            fn=_counting(trace, {"revenue": 100}),
        )
        trace.statuses.append(result.cache_status)
        trace.values.append(result.value)


async def _dependency_change(cl: ComputeLayer, trace: Trace) -> None:
    for version in ("v1", "v1", "v2"):
        result = await cl.compute.run(
            name="analysis",
            inputs={"ticker": "NVDA"},
            dependencies=[cl.dep("financials:NVDA", version=version)],
            fn=_counting(trace, {"verdict": "buy"}),
        )
        trace.statuses.append(result.cache_status)


async def _prompt_change(cl: ComputeLayer, trace: Trace) -> None:
    for prompt in ("careful analyst", "careful analyst", "terse analyst"):
        result = await cl.compute.run(
            name="overview",
            inputs={"ticker": "NVDA"},
            prompt=prompt,
            fn=_counting(trace, {"summary": "..."}),
        )
        trace.statuses.append(result.cache_status)


async def _forced(cl: ComputeLayer, trace: Trace) -> None:
    for force in (False, False, True, False):
        result = await cl.compute.run(
            name="latest_news",
            inputs={"ticker": "NVDA"},
            force=force,
            fn=_counting(trace, {"headline": "chips"}),
        )
        trace.statuses.append(result.cache_status)


async def _failure_is_not_reused(cl: ComputeLayer, trace: Trace) -> None:
    def boom() -> Any:
        trace.executions += 1
        raise RuntimeError("provider timed out")

    for _ in range(2):
        try:
            await cl.compute.run(name="flaky", inputs={"ticker": "NVDA"}, fn=boom)
        except RuntimeError:
            trace.statuses.append("FAILED")


async def _output_hash_propagation(cl: ComputeLayer, trace: Trace) -> None:
    """Benchmark scenario E (§46): upstream reruns, output identical."""

    async def pipeline(source_version: str) -> None:
        upstream = await cl.compute.run(
            name="financials",
            inputs={"ticker": "NVDA"},
            dependencies=[cl.dep("financials_source", version=source_version)],
            # Deliberately constant: the raw source changed, the normalized
            # output did not.
            fn=lambda: {"revenue": 100},
        )
        trace.statuses.append(upstream.cache_status)

        downstream = await cl.compute.run(
            name="financial_analysis",
            inputs={"financials": upstream},
            fn=_counting(trace, {"verdict": "buy"}),
        )
        trace.statuses.append(downstream.cache_status)

    await pipeline("v2")
    await pipeline("v3")


async def _changed_output_invalidates(cl: ComputeLayer, trace: Trace) -> None:
    async def pipeline(source_version: str, revenue: int) -> None:
        upstream = await cl.compute.run(
            name="financials",
            inputs={"ticker": "NVDA"},
            dependencies=[cl.dep("financials_source", version=source_version)],
            fn=lambda: {"revenue": revenue},
        )
        trace.statuses.append(upstream.cache_status)

        downstream = await cl.compute.run(
            name="financial_analysis",
            inputs={"financials": upstream},
            fn=_counting(trace, {"verdict": revenue}),
        )
        trace.statuses.append(downstream.cache_status)

    await pipeline("v2", 100)
    await pipeline("v3", 200)


async def _reusable_false(cl: ComputeLayer, trace: Trace) -> None:
    for _ in range(2):
        result = await cl.compute.run(
            name="always_fresh",
            inputs={"ticker": "NVDA"},
            reusable=False,
            fn=_counting(trace, {"n": 1}),
        )
        trace.statuses.append(result.cache_status)


SCENARIOS: list[Scenario] = [
    Scenario(
        name="identical_rerun",
        description="Nothing changed: everything after the first call is reused.",
        body=_identical_rerun,
        expected_statuses=("MISS", "HIT", "HIT"),
        expected_executions=1,
    ),
    Scenario(
        name="dependency_change",
        description="A changed dependency version invalidates the fingerprint.",
        body=_dependency_change,
        expected_statuses=("MISS", "HIT", "STALE"),
        expected_executions=2,
    ),
    Scenario(
        name="prompt_change",
        description="Changing the prompt invalidates the computation (§23).",
        body=_prompt_change,
        expected_statuses=("MISS", "HIT", "STALE"),
        expected_executions=2,
    ),
    Scenario(
        name="forced",
        description="force=True executes, and its result becomes the latest (§21).",
        body=_forced,
        expected_statuses=("MISS", "HIT", "FORCED", "HIT"),
        expected_executions=2,
    ),
    Scenario(
        name="failure_is_not_reused",
        description="Failed computations must never be reused (§3).",
        body=_failure_is_not_reused,
        expected_statuses=("FAILED", "FAILED"),
        expected_executions=2,
    ),
    Scenario(
        name="output_hash_propagation",
        description=(
            "Upstream re-executes but produces an identical output, so the "
            "downstream computation stays reusable (§19, §46)."
        ),
        body=_output_hash_propagation,
        expected_statuses=("MISS", "MISS", "STALE", "HIT"),
        expected_executions=1,
    ),
    Scenario(
        name="changed_output_invalidates",
        description="A changed upstream output invalidates downstream (§19).",
        body=_changed_output_invalidates,
        expected_statuses=("MISS", "MISS", "STALE", "STALE"),
        expected_executions=2,
    ),
    Scenario(
        name="reusable_false",
        description="reusable=False rows are recorded but never reused (§56).",
        body=_reusable_false,
        expected_statuses=("MISS", "STALE"),
        expected_executions=2,
    ),
]
