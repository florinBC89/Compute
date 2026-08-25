"""The API must produce exactly the traces the reference backend produces.

This is the test that stops the PostgreSQL implementation and the in-memory
reference implementation from drifting apart. A drift here means one of them
reuses something the other does not -- incorrect deterministic reuse, which
§61 calls the one unacceptable failure.
"""

from __future__ import annotations

import pytest

from computelayer.conformance import SCENARIOS, run_scenario


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
async def test_scenario_matches_expected_trace(scenario, cl) -> None:
    trace = await run_scenario(scenario, cl)

    assert tuple(trace.statuses) == scenario.expected_statuses, scenario.description
    assert trace.executions == scenario.expected_executions, scenario.description
