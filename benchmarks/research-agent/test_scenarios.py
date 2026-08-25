"""The benchmark as a test (spec §49).

Acceptance criteria are only worth anything if a regression trips them, so the
five scenarios run in CI alongside the unit suite:

    cd benchmarks/research-agent && python -m unittest -v

Two of these are also the last line of defence for the §13 and §19 deviations
documented in the top-level README. Reintroducing ``computation_id`` into the
hashed compute reference drops scenarios B and E from 100% cost reduction to
0%, with every downstream step recomputing -- verified by deliberately
reverting the fix.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from computelayer import CacheStatus  # noqa: E402

from scenarios import SCENARIOS, execute  # noqa: E402


class AcceptanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_scenario_meets_its_acceptance_criteria(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(scenario=f"{scenario.name} {scenario.label}"):
                result = await execute(scenario)
                self.assertTrue(
                    result.passed,
                    f"{scenario.label}: {'; '.join(result.failures)}",
                )

    async def test_identical_rerun_avoids_at_least_95_percent(self) -> None:
        """§49 criterion 1."""
        result = await execute(next(s for s in SCENARIOS if s.name == "B"))
        self.assertGreaterEqual(result.cost_reduction, 0.95)
        self.assertEqual(result.actual.executed, 0)

    async def test_single_branch_update_avoids_at_least_40_percent(self) -> None:
        """§49 criterion 2, on both the news and the financials branch."""
        for name in ("C", "D"):
            with self.subTest(scenario=name):
                result = await execute(next(s for s in SCENARIOS if s.name == name))
                self.assertGreaterEqual(result.cost_reduction, 0.40)
                self.assertEqual(result.actual.executed, 4)
                self.assertEqual(result.actual.reused, 6)

    async def test_unchanged_output_hash_stops_downstream_invalidation(self) -> None:
        """§49 criterion 4, and the whole point of scenario E (§46)."""
        result = await execute(next(s for s in SCENARIOS if s.name == "E"))

        statuses = result.actual.statuses
        self.assertNotEqual(
            statuses["financials"],
            CacheStatus.HIT,
            "the restated filing must force financials to re-execute",
        )
        for downstream in (
            "financial_analysis",
            "valuation",
            "final_report",
            "overview",
            "competitive_analysis",
            "news_analysis",
        ):
            self.assertEqual(
                statuses[downstream],
                CacheStatus.HIT,
                f"{downstream} recomputed even though its inputs are unchanged",
            )

    async def test_nothing_is_reused_when_a_dependency_genuinely_changed(self) -> None:
        """§49 criterion 3 -- the criterion that actually matters.

        Scenario D changes the figures, so every computation downstream of
        financials must recompute. A pass here that also passed scenario E is
        what distinguishes real propagation from simply reusing everything.
        """
        result = await execute(next(s for s in SCENARIOS if s.name == "D"))
        statuses = result.actual.statuses
        for downstream in ("financial_analysis", "valuation", "final_report"):
            self.assertNotEqual(
                statuses[downstream],
                CacheStatus.HIT,
                f"{downstream} was reused despite a changed upstream output",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
