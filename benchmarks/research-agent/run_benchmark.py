#!/usr/bin/env python3
"""ComputeLayer research-agent benchmark (spec §41-§49).

    python benchmarks/research-agent/run_benchmark.py --all
    python benchmarks/research-agent/run_benchmark.py --scenario C
    python benchmarks/research-agent/run_benchmark.py --all --json results.json

Runs entirely on the in-memory backend, so it needs no database, no Redis and
no provider key. Every figure is reproducible: same inputs, same numbers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import ScenarioResult  # noqa: E402
from scenarios import SCENARIOS, execute  # noqa: E402

WIDTH = 52


def _row(label: str, value: str) -> str:
    return f"{label:<28}{value:>{WIDTH - 28}}"


def _money(value: float) -> str:
    return f"${value:,.2f}"


def render(result: ScenarioResult) -> str:
    baseline, actual = result.baseline, result.actual
    lines = [
        "ComputeLayer Research Benchmark",
        "─" * WIDTH,
        "",
        f"Scenario:{'':<19}{result.label:>{WIDTH - 28}}",
        "",
        _row("Computations", str(actual.computations)),
        _row("Executed", str(actual.executed)),
        _row("Reused", str(actual.reused)),
        "",
        _row("LLM calls baseline", str(baseline.llm_calls)),
        _row("LLM calls actual", str(actual.llm_calls)),
        _row("Tool calls baseline", str(baseline.tool_calls)),
        _row("Tool calls actual", str(actual.tool_calls)),
        "",
        _row("Tokens baseline", f"{baseline.total_tokens:,}"),
        _row("Tokens actual", f"{actual.total_tokens:,}"),
        _row("Tokens avoided", f"{result.tokens_avoided:,}"),
        "",
        _row("Baseline cost", _money(baseline.cost_usd)),
        _row("Actual cost", _money(actual.cost_usd)),
        _row("Saved", _money(result.cost_avoided)),
        _row("Cost reduction", f"{result.cost_reduction:.1%}"),
        "",
        _row("Baseline latency", f"{baseline.latency_ms / 1000:,.1f}s"),
        _row("Actual latency", f"{actual.latency_ms / 1000:,.1f}s"),
        _row("Latency reduction", f"{result.latency_reduction:.1%}"),
        "",
        _row("Hit rate", f"{actual.hit_rate:.1%}"),
        "",
        f"RESULT:{'':<21}{'PASS' if result.passed else 'FAIL':>{WIDTH - 28}}",
    ]
    if not result.passed:
        lines.append("")
        for problem in result.failures:
            lines.append(f"  ! {problem}")
    return "\n".join(lines)


def render_steps(result: ScenarioResult) -> str:
    marker = {
        "HIT": "reused",
        "MISS": "computed",
        "STALE": "recomputed",
        "FORCED": "forced",
    }
    lines = ["", "  step                    outcome", "  " + "─" * (WIDTH - 2)]
    for name, status in result.actual.statuses.items():
        lines.append(f"  {name:<24}{marker.get(status, status)}")
    return "\n".join(lines)


def render_summary(results: list[ScenarioResult]) -> str:
    lines = [
        "",
        "═" * 74,
        "SUMMARY",
        "═" * 74,
        "",
        f"{'':2}{'scenario':<32}{'executed':>9}{'reused':>8}"
        f"{'saved':>10}{'reduction':>11}{'':>4}",
        "  " + "─" * 70,
    ]
    for result in results:
        lines.append(
            f"{'':2}{result.name + '  ' + result.label:<32}"
            f"{result.actual.executed:>9}{result.actual.reused:>8}"
            f"{_money(result.cost_avoided):>10}"
            f"{result.cost_reduction:>10.1%}"
            f"{'  PASS' if result.passed else '  FAIL':>6}"
        )

    passed = sum(1 for result in results if result.passed)
    lines += [
        "",
        f"  {passed}/{len(results)} scenarios pass the §49 acceptance criteria.",
        "",
        "  Latency figures are modelled, not measured: the benchmark uses a",
        "  deterministic stand-in for the model rather than sleeping through",
        "  real provider latency. Token counts, costs and reuse decisions are",
        "  produced by the real code path.",
    ]
    return "\n".join(lines)


def as_dict(result: ScenarioResult) -> dict:
    return {
        "scenario": result.name,
        "label": result.label,
        "description": result.description,
        "passed": result.passed,
        "failures": result.failures,
        "statuses": result.actual.statuses,
        "computations": result.actual.computations,
        "executed": result.actual.executed,
        "reused": result.actual.reused,
        "hit_rate": round(result.actual.hit_rate, 4),
        "baseline": {
            "tokens": result.baseline.total_tokens,
            "cost_usd": round(result.baseline.cost_usd, 6),
            "llm_calls": result.baseline.llm_calls,
            "tool_calls": result.baseline.tool_calls,
            "modelled_latency_ms": result.baseline.latency_ms,
        },
        "actual": {
            "tokens": result.actual.total_tokens,
            "cost_usd": round(result.actual.cost_usd, 6),
            "llm_calls": result.actual.llm_calls,
            "tool_calls": result.actual.tool_calls,
            "modelled_latency_ms": result.actual.latency_ms,
        },
        "avoided": {
            "tokens": result.tokens_avoided,
            "cost_usd": round(result.cost_avoided, 6),
            "cost_reduction": round(result.cost_reduction, 4),
            "llm_calls": result.llm_calls_avoided,
            "tool_calls": result.tool_calls_avoided,
            "modelled_latency_ms": result.latency_avoided_ms,
        },
    }


async def main_async(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="run every scenario")
    parser.add_argument("--scenario", help="run one scenario by letter (A-E)")
    parser.add_argument("--json", help="also write results to this path")
    parser.add_argument("--steps", action="store_true", help="show per-step outcomes")
    args = parser.parse_args(argv)

    selected = SCENARIOS
    if args.scenario:
        wanted = args.scenario.strip().upper()
        selected = [s for s in SCENARIOS if s.name == wanted]
        if not selected:
            parser.error(f"unknown scenario {args.scenario!r}; expected one of A-E")
    elif not args.all:
        parser.error("pass --all or --scenario X")

    results: list[ScenarioResult] = []
    for scenario in selected:
        result = await execute(scenario)
        results.append(result)
        print(render(result))
        if args.steps:
            print(render_steps(result))
        print()

    if len(results) > 1:
        print(render_summary(results))

    if args.json:
        Path(args.json).write_text(
            json.dumps([as_dict(r) for r in results], indent=2), encoding="utf-8"
        )
        print(f"\nWrote {args.json}")

    return 0 if all(result.passed for result in results) else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(main_async(argv))


if __name__ == "__main__":
    raise SystemExit(main())
