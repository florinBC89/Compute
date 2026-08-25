"""The ten-computation research workflow (spec §42, §43).

                     company_profile
                           |
                           v
                        overview
                           |
          +----------------+------------------+
          v                v                  v
     financials        competitors           news
          |                |                  |
          v                v                  v
 financial_analysis competitive_analysis  news_analysis
          |                |                  |
          +--------------+-+------------------+
                         v
                     valuation
                         |
                         v
                    final_report

Four fetches (deterministic, counted as tool calls) and six analyses (one LLM
call each). Downstream edges are never declared: passing a ``ComputeResult``
into another computation's inputs registers the dependency automatically (§12),
which is also what makes output-hash propagation work.

Fixture versions are declared as *dependencies* rather than inputs. §43 lists
them as inputs, but a dependency is the more accurate description -- the
version identifies external state, not the question being asked -- and it means
scenarios D and E differ only in whether the normalized output changes, which
is exactly the distinction being measured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from computelayer import ComputeLayer, ComputeResult

import fixtures
from fake_llm import MODEL, TOOL_LATENCY_MS, DeterministicLLM

ANALYST_PROMPT = (
    "You are an equity research analyst. Be precise, cite figures from the "
    "supplied context, and never speculate beyond it."
)


@dataclass
class SourceVersions:
    """Which version of each external source the world is currently at."""

    financials: str = "v1"
    competitors: str = "v1"
    news: str = "v1"

    def replace(self, **changes: str) -> "SourceVersions":
        return SourceVersions(**{**self.__dict__, **changes})


@dataclass
class WorkflowRun:
    results: dict[str, ComputeResult] = field(default_factory=dict)
    tool_calls: int = 0
    #: Modelled per-step latency, keyed by step name.
    modelled_latency: dict[str, int] = field(default_factory=dict)

    @property
    def statuses(self) -> dict[str, str]:
        return {name: result.cache_status for name, result in self.results.items()}


STEP_NAMES = (
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
)

#: Steps whose execution costs an LLM call.
LLM_STEPS = frozenset(
    {
        "overview",
        "financial_analysis",
        "competitive_analysis",
        "news_analysis",
        "valuation",
        "final_report",
    }
)

#: Steps whose execution costs a tool/API call.
TOOL_STEPS = frozenset({"company_profile", "financials", "competitors", "news"})


async def run_workflow(
    cl: ComputeLayer, versions: SourceVersions, ticker: str = fixtures.TICKER
) -> WorkflowRun:
    """Execute one full research pass and return every step's result."""
    llm = DeterministicLLM()
    run = WorkflowRun()

    def record(name: str, result: ComputeResult) -> ComputeResult:
        run.results[name] = result
        return result

    # -- fetches ----------------------------------------------------------

    def fetch(name: str, value: Any) -> Any:
        run.tool_calls += 1
        run.modelled_latency[name] = TOOL_LATENCY_MS
        return value

    company_profile = record(
        "company_profile",
        await cl.compute.run(
            name="company_profile",
            inputs={"ticker": ticker},
            fn=lambda: fetch("company_profile", fixtures.profile(ticker)),
        ),
    )

    financials = record(
        "financials",
        await cl.compute.run(
            name="financials",
            inputs={"ticker": ticker},
            dependencies=[
                cl.dep(f"financials_source:{ticker}", version=versions.financials)
            ],
            fn=lambda: fetch("financials", fixtures.financials(versions.financials)),
        ),
    )

    competitors = record(
        "competitors",
        await cl.compute.run(
            name="competitors",
            inputs={"ticker": ticker},
            dependencies=[
                cl.dep(f"industry_source:{ticker}", version=versions.competitors)
            ],
            fn=lambda: fetch("competitors", fixtures.competitors(versions.competitors)),
        ),
    )

    news = record(
        "news",
        await cl.compute.run(
            name="news",
            inputs={"ticker": ticker},
            dependencies=[cl.dep(f"news_source:{ticker}", version=versions.news)],
            fn=lambda: fetch("news", fixtures.news(versions.news)),
        ),
    )

    # -- analyses ---------------------------------------------------------

    async def analyse(name: str, **context: Any) -> ComputeResult:
        result = await cl.compute.run(
            name=name,
            inputs=context,
            model=MODEL,
            prompt=ANALYST_PROMPT,
            fn=lambda: llm.complete(
                prompt=ANALYST_PROMPT,
                context={key: _value_of(value) for key, value in context.items()},
                task=name,
            ),
        )
        if name in llm.latency_by_task:
            run.modelled_latency[name] = llm.latency_by_task[name]
        return record(name, result)

    overview = await analyse("overview", profile=company_profile)
    financial_analysis = await analyse("financial_analysis", financials=financials)
    competitive_analysis = await analyse(
        "competitive_analysis", competitors=competitors
    )
    news_analysis = await analyse("news_analysis", news=news)

    valuation = await analyse(
        "valuation",
        financial_analysis=financial_analysis,
        competitive_analysis=competitive_analysis,
        news_analysis=news_analysis,
    )

    await analyse(
        "final_report",
        overview=overview,
        financial_analysis=financial_analysis,
        competitive_analysis=competitive_analysis,
        news_analysis=news_analysis,
        valuation=valuation,
    )

    return run


def _value_of(value: Any) -> Any:
    """Unwrap a ComputeResult for the LLM prompt.

    The *result object* is what goes into ``inputs`` -- that is what registers
    the dependency and carries the output hash. The LLM only ever sees the
    value.
    """
    return value.value if isinstance(value, ComputeResult) else value
