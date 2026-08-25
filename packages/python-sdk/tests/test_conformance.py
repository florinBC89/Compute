"""The shared backend conformance suite, run against the reference backend.

``apps/api/tests/test_conformance.py`` runs the identical suite against the
PostgreSQL-backed API. Both must produce the same traces.
"""

from __future__ import annotations

import unittest

from computelayer import ComputeLayer
from computelayer.conformance import SCENARIOS, run_scenario
from computelayer.testing import LocalBackend


class ConformanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_scenario_matches_its_expected_trace(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario.name):
                client = ComputeLayer(project="conformance", transport=LocalBackend())
                trace = await run_scenario(scenario, client)
                self.assertEqual(
                    tuple(trace.statuses),
                    scenario.expected_statuses,
                    f"{scenario.name}: {scenario.description}",
                )
                self.assertEqual(
                    trace.executions,
                    scenario.expected_executions,
                    f"{scenario.name}: wrong number of executions",
                )
                await client.aclose()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
