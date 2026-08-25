"""Benchmark accounting (spec §47).

Every scenario is measured twice against the same world state:

*baseline*
    the workflow run against an empty cache, so all ten computations execute.
    This is what the agent costs today, without ComputeLayer.

*actual*
    the same workflow against the warm cache.

Measuring the baseline per scenario rather than reusing scenario A's numbers
matters: after a fixture changes, the uncached cost of the run is not the same
as the uncached cost of the cold run, and comparing against the wrong figure
would flatter the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from computelayer import CacheStatus

from workflow import LLM_STEPS, TOOL_STEPS, WorkflowRun


@dataclass
class RunTotals:
    computations: int = 0
    executed: int = 0
    reused: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    statuses: dict[str, str] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def hit_rate(self) -> float:
        return self.reused / self.computations if self.computations else 0.0


def summarize(run: WorkflowRun, modelled_latency: dict[str, int]) -> RunTotals:
    """Fold one workflow pass into totals."""
    totals = RunTotals()
    for name, result in run.results.items():
        totals.computations += 1
        totals.statuses[name] = result.cache_status

        if result.cache_status == CacheStatus.HIT:
            totals.reused += 1
            continue

        totals.executed += 1
        totals.input_tokens += result.input_tokens
        totals.output_tokens += result.output_tokens
        totals.cost_usd += result.cost_usd
        totals.latency_ms += modelled_latency.get(name, 0)
        if name in LLM_STEPS:
            totals.llm_calls += 1
        if name in TOOL_STEPS:
            totals.tool_calls += 1

    return totals


@dataclass
class ScenarioResult:
    name: str
    label: str
    description: str
    baseline: RunTotals
    actual: RunTotals
    expected_executed: frozenset[str] | None = None
    acceptance_note: str = ""
    minimum_cost_reduction: float | None = None

    # -- derived ----------------------------------------------------------

    @property
    def tokens_avoided(self) -> int:
        return self.baseline.total_tokens - self.actual.total_tokens

    @property
    def cost_avoided(self) -> float:
        return self.baseline.cost_usd - self.actual.cost_usd

    @property
    def cost_reduction(self) -> float:
        if not self.baseline.cost_usd:
            return 0.0
        return self.cost_avoided / self.baseline.cost_usd

    @property
    def latency_avoided_ms(self) -> int:
        return self.baseline.latency_ms - self.actual.latency_ms

    @property
    def latency_reduction(self) -> float:
        if not self.baseline.latency_ms:
            return 0.0
        return self.latency_avoided_ms / self.baseline.latency_ms

    @property
    def llm_calls_avoided(self) -> int:
        return self.baseline.llm_calls - self.actual.llm_calls

    @property
    def tool_calls_avoided(self) -> int:
        return self.baseline.tool_calls - self.actual.tool_calls

    @property
    def executed_steps(self) -> frozenset[str]:
        return frozenset(
            name
            for name, status in self.actual.statuses.items()
            if status != CacheStatus.HIT
        )

    # -- acceptance (§49) --------------------------------------------------

    @property
    def failures(self) -> list[str]:
        problems: list[str] = []

        if self.expected_executed is not None:
            unexpected = self.executed_steps - self.expected_executed
            missing = self.expected_executed - self.executed_steps
            if unexpected:
                problems.append(
                    "recomputed without cause: " + ", ".join(sorted(unexpected))
                )
            if missing:
                problems.append(
                    "reused when it should have recomputed: "
                    + ", ".join(sorted(missing))
                )

        if self.minimum_cost_reduction is not None:
            if self.cost_reduction < self.minimum_cost_reduction:
                problems.append(
                    f"cost reduction {self.cost_reduction:.1%} below the "
                    f"{self.minimum_cost_reduction:.0%} target"
                )

        return problems

    @property
    def passed(self) -> bool:
        return not self.failures
