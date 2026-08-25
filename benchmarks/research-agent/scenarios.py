"""The five benchmark scenarios (spec §44, §45, §46).

Each scenario is: put the cache in some state, change the world, then measure
the next run twice -- once against an empty cache (the baseline: what the agent
costs without ComputeLayer) and once against the warm cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from computelayer import ComputeLayer
from computelayer.testing import LocalBackend

from metrics import ScenarioResult, summarize
from workflow import SourceVersions, run_workflow

INITIAL = SourceVersions(financials="v1", competitors="v1", news="v1")


@dataclass
class Scenario:
    name: str
    label: str
    description: str
    #: State the cache is warmed with. ``None`` means start cold.
    warm_with: SourceVersions | None
    #: State the measured run happens at.
    measure_at: SourceVersions
    expected_executed: frozenset[str] | None = None
    minimum_cost_reduction: float | None = None
    acceptance_note: str = ""
    extra_checks: list[Callable[[ScenarioResult], str | None]] = field(
        default_factory=list
    )


def _client() -> ComputeLayer:
    return ComputeLayer(project="benchmark", transport=LocalBackend())


async def execute(scenario: Scenario) -> ScenarioResult:
    # -- baseline: the same world state, but nothing cached ---------------
    baseline_client = _client()
    baseline_run = await run_workflow(baseline_client, scenario.measure_at)
    baseline = summarize(baseline_run, baseline_run.modelled_latency)
    await baseline_client.aclose()

    # -- actual: warm the cache, change the world, measure -----------------
    client = _client()
    if scenario.warm_with is not None:
        warm_run = await run_workflow(client, scenario.warm_with)
        # Latency of the warming pass is not part of the measurement.
        del warm_run

    actual_run = await run_workflow(client, scenario.measure_at)
    # Steps that were reused this pass contribute no latency, but the baseline
    # needs a figure for every step, so fall back to the baseline's timings.
    latency = {**baseline_run.modelled_latency, **actual_run.modelled_latency}
    actual = summarize(actual_run, latency)
    await client.aclose()

    return ScenarioResult(
        name=scenario.name,
        label=scenario.label,
        description=scenario.description,
        baseline=baseline,
        actual=actual,
        expected_executed=scenario.expected_executed,
        minimum_cost_reduction=scenario.minimum_cost_reduction,
        acceptance_note=scenario.acceptance_note,
    )


ALL_STEPS = frozenset(
    {
        "company_profile",
        "financials",
        "competitors",
        "news",
        "overview",
        "financial_analysis",
        "competitive_analysis",
        "news_analysis",
        "valuation",
        "final_report",
    }
)


SCENARIOS: list[Scenario] = [
    Scenario(
        name="A",
        label="COLD_RUN",
        description="Nothing has ever been computed. Everything executes.",
        warm_with=None,
        measure_at=INITIAL,
        expected_executed=ALL_STEPS,
        acceptance_note="Establishes the baseline cost of one research pass.",
    ),
    Scenario(
        name="B",
        label="IDENTICAL_RERUN",
        description="The same question, nothing in the world changed.",
        warm_with=INITIAL,
        measure_at=INITIAL,
        expected_executed=frozenset(),
        minimum_cost_reduction=0.95,
        acceptance_note="§49: an identical rerun must avoid >=95% of compute.",
    ),
    Scenario(
        name="C",
        label="NEWS_UPDATE",
        description="Two new headlines. Nothing else moved.",
        warm_with=INITIAL,
        measure_at=INITIAL.replace(news="v2"),
        expected_executed=frozenset(
            {"news", "news_analysis", "valuation", "final_report"}
        ),
        minimum_cost_reduction=0.40,
        acceptance_note="§44: the profile, financial and competitive branches reuse.",
    ),
    Scenario(
        name="D",
        label="FINANCIALS_UPDATE",
        description="A new filing changes the numbers.",
        warm_with=INITIAL,
        measure_at=INITIAL.replace(financials="v2"),
        expected_executed=frozenset(
            {"financials", "financial_analysis", "valuation", "final_report"}
        ),
        minimum_cost_reduction=0.40,
        acceptance_note="§45: the news and competitive branches reuse.",
    ),
    Scenario(
        name="E",
        label="UPSTREAM_CHURN_STABLE_OUTPUT",
        description=(
            "The filing is restated -- reordered keys, a renamed field, figures "
            "in thousands -- and normalizes to an identical object."
        ),
        warm_with=INITIAL.replace(financials="v2"),
        measure_at=INITIAL.replace(financials="v3"),
        expected_executed=frozenset({"financials"}),
        minimum_cost_reduction=0.95,
        acceptance_note=(
            "§46: financials must re-execute, and because its output hash is "
            "unchanged, everything downstream must stay reusable. This is what "
            "proves propagation is driven by output hashes, not by dependency "
            "versions."
        ),
    ),
]
