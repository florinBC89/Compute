"""Command-line interface (spec §53).

    computelayer run list
    computelayer run show <id>
    computelayer explain <computation_id>
    computelayer benchmark research-agent
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from computelayer.client import ComputeLayer


def _client() -> ComputeLayer:
    return ComputeLayer(
        api_key=os.getenv("COMPUTELAYER_API_KEY"),
        project=os.getenv("COMPUTELAYER_PROJECT", "default"),
        base_url=os.getenv("COMPUTELAYER_API_URL"),
    )


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, default=str))


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


async def _run_show(run_id: str) -> int:
    async with _client() as cl:
        summary = await cl.get_run(run_id)
        graph = await cl.get_run_graph(run_id)

    reuse = summary["hits"] / summary["computations"] if summary["computations"] else 0
    print(f"Run {run_id}")
    print(f"  status        {summary['status']}")
    print(f"  computations  {summary['computations']}")
    print(
        f"  reuse         {summary['hits']} hit / "
        f"{summary['misses']} miss / {summary['stale']} stale  ({reuse:.1%})"
    )
    print(f"  cost          ${summary['total_cost_usd']:.4f}")
    print(f"  saved         ${summary['saved_usd']:.4f}")
    print()
    for node in graph["nodes"]:
        marker = {"HIT": "reused", "MISS": "computed", "STALE": "recomputed",
                  "FORCED": "forced"}.get(node["status"], node["status"])
        print(
            f"  {node['name']:<24} {marker:<11} "
            f"${node['cost_usd']:.4f}  saved ${node['saved_usd']:.4f}"
        )
    return 0


async def _run_list() -> int:
    async with _client() as cl:
        metrics = await cl.get_metrics()
    _print(metrics)
    print(
        "\nNote: listing individual runs requires GET /v1/runs, which is not part "
        "of the V0.1 API surface. Project metrics are shown instead.",
        file=sys.stderr,
    )
    return 0


async def _explain(computation_id: str) -> int:
    async with _client() as cl:
        explanation = await cl.explain(computation_id)

    if not explanation["changes"]:
        print(f"{explanation['name']} was {explanation['cache_status']}.")
        if explanation["previous_computation_id"] is None:
            print("No earlier version of this computation exists.")
        return 0

    print(f"{explanation['name']} was recomputed because:")
    for change in explanation["changes"]:
        kind = change["kind"]
        if kind.startswith("dependency"):
            print(f"\n  dependency\n    {change.get('key')}")
            if kind == "dependency_changed":
                print(f"  changed:\n    old:\n      {change['old']}")
                print(f"    new:\n      {change['new']}")
            elif kind == "dependency_added":
                print(f"  was added:\n    {change['new']}")
            else:
                print("  was removed")
        else:
            field = kind.removesuffix("_changed")
            print(f"\n  {field} changed:")
            print(f"    old: {change.get('old')}")
            print(f"    new: {change.get('new')}")
    return 0


def _benchmark(name: str, argv: list[str]) -> int:
    if name != "research-agent":
        print(f"unknown benchmark {name!r}", file=sys.stderr)
        return 2
    try:
        from benchmarks.research_agent.run_benchmark import main as run_benchmark
    except ImportError:
        import pathlib
        import runpy

        root = pathlib.Path(__file__).resolve().parents[3]
        script = root / "benchmarks" / "research-agent" / "run_benchmark.py"
        if not script.exists():
            print(
                "benchmark not found; run it from a checkout of the monorepo:\n"
                "  python benchmarks/research-agent/run_benchmark.py --all",
                file=sys.stderr,
            )
            return 2
        sys.argv = [str(script), *argv]
        runpy.run_path(str(script), run_name="__main__")
        return 0
    return int(run_benchmark(argv) or 0)


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="computelayer")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="inspect runs")
    run_sub = run.add_subparsers(dest="run_command", required=True)
    run_sub.add_parser("list", help="project-level reuse metrics")
    show = run_sub.add_parser("show", help="show one run and its graph")
    show.add_argument("run_id")

    explain = sub.add_parser("explain", help="why did this computation run?")
    explain.add_argument("computation_id")

    benchmark = sub.add_parser("benchmark", help="run a benchmark")
    benchmark.add_argument("name", nargs="?", default="research-agent")
    benchmark.add_argument("rest", nargs=argparse.REMAINDER)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "run":
        if args.run_command == "list":
            return asyncio.run(_run_list())
        return asyncio.run(_run_show(args.run_id))
    if args.command == "explain":
        return asyncio.run(_explain(args.computation_id))
    if args.command == "benchmark":
        return _benchmark(args.name, args.rest)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
