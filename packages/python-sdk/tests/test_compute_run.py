"""End-to-end ``compute.run`` behaviour against the reference backend.

Covers the mandatory test groups of §50 that involve execution: HIT, MISS,
STALE, FORCED, TTL expiry, failure handling, nested computation dependencies,
output-hash propagation (§19, benchmark scenario E) and concurrency (§37).
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import unittest

from computelayer import CacheStatus, ComputeLayer
from computelayer.dependency import DependencyType
from computelayer.testing import LocalBackend


class Clock:
    """Manually advanced clock so TTL behaviour is testable without sleeping."""

    def __init__(self) -> None:
        self.now = _dt.datetime(2026, 8, 25, 12, 0, 0, tzinfo=_dt.timezone.utc)

    def __call__(self) -> _dt.datetime:
        self.now += _dt.timedelta(microseconds=1)  # keep ordering strict
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += _dt.timedelta(seconds=seconds)


class Counter:
    def __init__(self) -> None:
        self.calls = 0

    def bump(self) -> int:
        self.calls += 1
        return self.calls


class ComputeRunTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.backend = LocalBackend(clock=self.clock)
        self.cl = ComputeLayer(project="tests", transport=self.backend)


class BasicLifecycleTests(ComputeRunTestCase):
    async def test_miss_then_hit(self) -> None:
        counter = Counter()

        async def call() -> dict:
            return await self.cl.compute.run(
                name="financials",
                inputs={"ticker": "NVDA"},
                fn=lambda: {"revenue": counter.bump()},
            )

        first = await call()
        second = await call()

        self.assertEqual(first.cache_status, CacheStatus.MISS)
        self.assertEqual(second.cache_status, CacheStatus.HIT)
        self.assertEqual(counter.calls, 1, "the function must not run twice")
        self.assertEqual(second.value, {"revenue": 1})
        self.assertEqual(first.output_hash, second.output_hash)

    async def test_changed_input_is_stale_not_miss(self) -> None:
        await self.cl.compute.run(
            name="financials", inputs={"ticker": "NVDA", "v": 1}, fn=lambda: {"a": 1}
        )
        changed = await self.cl.compute.run(
            name="financials", inputs={"ticker": "NVDA", "v": 2}, fn=lambda: {"a": 2}
        )
        # Different identity inputs => a genuinely new logical computation.
        self.assertEqual(changed.cache_status, CacheStatus.MISS)

    async def test_changed_dependency_is_stale(self) -> None:
        counter = Counter()

        async def call(version: str):
            return await self.cl.compute.run(
                name="analysis",
                inputs={"ticker": "NVDA"},
                dependencies=[self.cl.dep("financials:NVDA", version=version)],
                fn=lambda: {"n": counter.bump()},
            )

        await call("v1")
        second = await call("v2")

        self.assertEqual(second.cache_status, CacheStatus.STALE)
        self.assertEqual(counter.calls, 2)

    async def test_changed_prompt_is_stale(self) -> None:
        async def call(prompt: str):
            return await self.cl.compute.run(
                name="analysis",
                inputs={"ticker": "NVDA"},
                prompt=prompt,
                fn=lambda: {"a": 1},
            )

        await call("You are a careful analyst.")
        second = await call("You are a terse analyst.")
        self.assertEqual(second.cache_status, CacheStatus.STALE)

    async def test_changed_model_is_stale(self) -> None:
        async def call(model: str):
            return await self.cl.compute.run(
                name="analysis",
                inputs={"ticker": "NVDA"},
                model=model,
                fn=lambda: {"a": 1},
            )

        await call("openai/gpt-4o")
        second = await call("openai/gpt-4o-mini")
        self.assertEqual(second.cache_status, CacheStatus.STALE)

    async def test_forced_execution_bypasses_the_cache(self) -> None:
        counter = Counter()

        async def call(force: bool = False):
            return await self.cl.compute.run(
                name="latest_news",
                inputs={"ticker": "NVDA"},
                force=force,
                fn=lambda: {"n": counter.bump()},
            )

        await call()
        forced = await call(force=True)
        after = await call()

        self.assertEqual(forced.cache_status, CacheStatus.FORCED)
        self.assertEqual(counter.calls, 2)
        # The forced result becomes the latest valid computation (§21).
        self.assertEqual(after.cache_status, CacheStatus.HIT)
        self.assertEqual(after.value, {"n": 2})

    async def test_reusable_false_is_never_hit(self) -> None:
        counter = Counter()

        async def call():
            return await self.cl.compute.run(
                name="always_fresh",
                inputs={"ticker": "NVDA"},
                reusable=False,
                fn=lambda: {"n": counter.bump()},
            )

        await call()
        second = await call()
        self.assertEqual(second.cache_status, CacheStatus.STALE)
        self.assertEqual(counter.calls, 2)


class TTLTests(ComputeRunTestCase):
    async def test_expired_computation_becomes_stale(self) -> None:
        counter = Counter()

        async def call():
            return await self.cl.compute.run(
                name="latest_news",
                inputs={"ticker": "NVDA"},
                ttl=3600,
                fn=lambda: {"n": counter.bump()},
            )

        first = await call()
        self.assertEqual(first.cache_status, CacheStatus.MISS)

        self.clock.advance(1800)
        self.assertEqual((await call()).cache_status, CacheStatus.HIT)

        self.clock.advance(3600)
        expired = await call()
        self.assertEqual(expired.cache_status, CacheStatus.STALE)
        self.assertEqual(counter.calls, 2)


class FailureTests(ComputeRunTestCase):
    async def test_failed_computations_are_never_reused(self) -> None:
        counter = Counter()

        async def call():
            def body():
                counter.bump()
                raise RuntimeError("provider timed out")

            return await self.cl.compute.run(
                name="flaky", inputs={"ticker": "NVDA"}, fn=body
            )

        with self.assertRaises(RuntimeError):
            await call()
        with self.assertRaises(RuntimeError):
            await call()

        self.assertEqual(counter.calls, 2)
        statuses = {row["status"] for row in self.backend.computations.values()}
        self.assertEqual(statuses, {"FAILED"})

    async def test_failure_is_recorded_with_its_error(self) -> None:
        async def body():
            raise TimeoutError("provider timed out")

        with self.assertRaises(TimeoutError):
            await self.cl.compute.run(name="flaky", inputs={}, fn=body)

        row = next(iter(self.backend.computations.values()))
        self.assertEqual(row["metadata"]["error_type"], "TimeoutError")
        self.assertIn("timed out", row["metadata"]["error_message"])

    async def test_success_after_failure_is_reusable(self) -> None:
        state = {"fail": True}

        def body():
            if state["fail"]:
                raise RuntimeError("nope")
            return {"ok": True}

        with self.assertRaises(RuntimeError):
            await self.cl.compute.run(name="retry", inputs={"a": 1}, fn=body)

        state["fail"] = False
        recovered = await self.cl.compute.run(name="retry", inputs={"a": 1}, fn=body)
        # MISS, not STALE: a failed attempt produced no result, so there is no
        # older version of this computation for the new one to be stale against.
        self.assertEqual(recovered.cache_status, CacheStatus.MISS)

        again = await self.cl.compute.run(name="retry", inputs={"a": 1}, fn=body)
        self.assertEqual(again.cache_status, CacheStatus.HIT)


class NestedDependencyTests(ComputeRunTestCase):
    """§12: a ComputeResult inside inputs becomes a COMPUTATION dependency."""

    async def test_dependency_is_inferred_from_inputs(self) -> None:
        upstream = await self.cl.compute.run(
            name="financials", inputs={"ticker": "NVDA"}, fn=lambda: {"revenue": 100}
        )
        downstream = await self.cl.compute.run(
            name="analysis",
            inputs={"ticker": "NVDA", "financials": upstream},
            fn=lambda: {"verdict": "buy"},
        )

        recorded = self.backend.dependencies[downstream.computation_id]
        self.assertEqual(len(recorded), 1)
        dependency = recorded[0]
        self.assertEqual(dependency["type"], DependencyType.COMPUTATION)
        self.assertEqual(dependency["version"], upstream.output_hash)
        self.assertEqual(dependency["source_computation_id"], upstream.computation_id)

    async def test_graph_edges_connect_upstream_to_downstream(self) -> None:
        async with self.cl.run() as run:
            upstream = await self.cl.compute.run(
                name="financials", inputs={"ticker": "NVDA"}, fn=lambda: {"revenue": 1}
            )
            await self.cl.compute.run(
                name="analysis",
                inputs={"financials": upstream},
                fn=lambda: {"verdict": "buy"},
            )

        graph = await self.cl.get_run_graph(run.id)
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(graph["edges"][0]["from"], upstream.computation_id)


class PropagationTests(ComputeRunTestCase):
    """§19 and benchmark scenario E (§46)."""

    async def _pipeline(self, source_version: str, revenue: int, counter: Counter):
        """financials -> analysis, where financials normalizes away noise."""
        financials = await self.cl.compute.run(
            name="financials",
            inputs={"ticker": "NVDA"},
            dependencies=[self.cl.dep("financials_source:NVDA", version=source_version)],
            fn=lambda: {"revenue": revenue},
        )
        analysis = await self.cl.compute.run(
            name="analysis",
            inputs={"financials": financials},
            fn=lambda: {"verdict": "buy", "n": counter.bump()},
        )
        return financials, analysis

    async def test_upstream_reruns_but_identical_output_keeps_downstream_hit(
        self,
    ) -> None:
        counter = Counter()

        first_up, first_down = await self._pipeline("v2", 100, counter)
        self.assertEqual(first_up.cache_status, CacheStatus.MISS)
        self.assertEqual(first_down.cache_status, CacheStatus.MISS)

        # The raw source changed, so financials must execute again...
        second_up, second_down = await self._pipeline("v3", 100, counter)
        self.assertEqual(second_up.cache_status, CacheStatus.STALE)
        # ...but it produced the same normalized output, so nothing downstream
        # needs to rerun. This is the whole basis of efficient propagation.
        self.assertEqual(first_up.output_hash, second_up.output_hash)
        self.assertEqual(second_down.cache_status, CacheStatus.HIT)
        self.assertEqual(counter.calls, 1)

    async def test_changed_upstream_output_invalidates_downstream(self) -> None:
        counter = Counter()

        await self._pipeline("v2", 100, counter)
        _, second_down = await self._pipeline("v3", 200, counter)

        self.assertEqual(second_down.cache_status, CacheStatus.STALE)
        self.assertEqual(counter.calls, 2)

    async def test_three_deep_chain_propagates(self) -> None:
        """A -> B -> C, with A's output unchanged, must leave C untouched."""
        counters = {"b": Counter(), "c": Counter()}

        async def chain(source_version: str, a_value: int):
            a = await self.cl.compute.run(
                name="A",
                inputs={},
                dependencies=[self.cl.dep("src", version=source_version)],
                fn=lambda: {"v": a_value},
            )
            b = await self.cl.compute.run(
                name="B", inputs={"a": a}, fn=lambda: {"v": counters["b"].bump()}
            )
            c = await self.cl.compute.run(
                name="C", inputs={"b": b}, fn=lambda: {"v": counters["c"].bump()}
            )
            return a, b, c

        await chain("v1", 1)
        _, b2, c2 = await chain("v2", 1)  # A reruns, same output

        self.assertEqual(b2.cache_status, CacheStatus.HIT)
        self.assertEqual(c2.cache_status, CacheStatus.HIT)
        self.assertEqual(counters["b"].calls, 1)
        self.assertEqual(counters["c"].calls, 1)


class DecoratorTests(ComputeRunTestCase):
    """§10."""

    async def test_decorator_caches_by_arguments(self) -> None:
        counter = Counter()
        cl = self.cl

        @cl.compute(name="financial_analysis", ttl=86400)
        async def financial_analysis(company: str, financials: dict) -> dict:
            return {"company": company, "n": counter.bump()}

        first = await financial_analysis("NVDA", {"revenue": 1})
        second = await financial_analysis("NVDA", {"revenue": 1})
        third = await financial_analysis("AMD", {"revenue": 1})

        self.assertEqual(first, {"company": "NVDA", "n": 1})
        self.assertEqual(second, {"company": "NVDA", "n": 1})
        self.assertEqual(third, {"company": "AMD", "n": 2})
        self.assertEqual(counter.calls, 2)

    async def test_positional_and_keyword_arguments_agree(self) -> None:
        counter = Counter()
        cl = self.cl

        @cl.compute()
        async def analyze(company: str, period: str = "FY2025") -> dict:
            return {"n": counter.bump()}

        await analyze("NVDA")
        await analyze(company="NVDA", period="FY2025")
        self.assertEqual(counter.calls, 1)

    async def test_compute_run_variant_exposes_the_result(self) -> None:
        cl = self.cl

        @cl.compute()
        async def analyze(company: str) -> dict:
            return {"ok": True}

        result = await analyze.compute_run("NVDA")
        self.assertEqual(result.cache_status, CacheStatus.MISS)
        again = await analyze.compute_run("NVDA")
        self.assertEqual(again.cache_status, CacheStatus.HIT)
        forced = await analyze.compute_run("NVDA", force=True)
        self.assertEqual(forced.cache_status, CacheStatus.FORCED)


class ConcurrencyTests(ComputeRunTestCase):
    """§37, §49: parallel identical executions must collapse to one."""

    async def test_stampede_collapses_to_a_single_execution(self) -> None:
        counter = Counter()

        async def body() -> dict:
            await asyncio.sleep(0.05)
            return {"n": counter.bump()}

        results = await asyncio.gather(
            *(
                self.cl.compute.run(
                    name="expensive", inputs={"ticker": "NVDA"}, fn=body
                )
                for _ in range(10)
            )
        )

        self.assertEqual(counter.calls, 1)
        statuses = [r.cache_status for r in results]
        self.assertEqual(statuses.count(CacheStatus.HIT), 9)
        self.assertEqual(statuses.count(CacheStatus.MISS), 1)


class RunAccountingTests(ComputeRunTestCase):
    """§27, §34."""

    async def test_savings_equal_the_reused_cost(self) -> None:
        from computelayer.context import LLMCall, record_llm_call

        def body() -> dict:
            record_llm_call(
                LLMCall(
                    model="openai/gpt-4o",
                    input_tokens=10_000,
                    output_tokens=1_200,
                    cost_usd=0.182,
                )
            )
            return {"ok": True}

        first = await self.cl.compute.run(name="analysis", inputs={"a": 1}, fn=body)
        second = await self.cl.compute.run(name="analysis", inputs={"a": 1}, fn=body)

        self.assertAlmostEqual(first.cost_usd, 0.182)
        self.assertEqual(first.saved_usd, 0.0)
        self.assertEqual(second.cost_usd, 0.0)
        self.assertAlmostEqual(second.saved_usd, 0.182)
        self.assertEqual(first.input_tokens, 10_000)
        self.assertEqual(second.input_tokens, 0)

    async def test_run_summary_counts_every_state(self) -> None:
        async with self.cl.run() as run:
            await self.cl.compute.run(name="a", inputs={"x": 1}, fn=lambda: {"v": 1})
            await self.cl.compute.run(name="a", inputs={"x": 1}, fn=lambda: {"v": 1})
            await self.cl.compute.run(name="b", inputs={"x": 1}, fn=lambda: {"v": 2})

        summary = run.summary
        self.assertEqual(summary["computations"], 3)
        self.assertEqual(summary["hits"], 1)
        self.assertEqual(summary["misses"], 2)
        self.assertEqual(summary["status"], "SUCCEEDED")

    async def test_failed_run_is_marked_failed(self) -> None:
        with self.assertRaises(RuntimeError):
            async with self.cl.run() as run:
                run_id = run.id
                raise RuntimeError("agent blew up")

        summary = await self.cl.get_run(run_id)
        self.assertEqual(summary["status"], "FAILED")


class SecretStorageTests(ComputeRunTestCase):
    """§56, §57: secrets participate in the fingerprint but are never stored."""

    async def test_secret_is_not_persisted(self) -> None:
        await self.cl.compute.run(
            name="call_api",
            inputs={"customer_id": "123", "api_token": self.cl.secret("super-secret")},
            fn=lambda: {"ok": True},
        )
        row = next(iter(self.backend.computations.values()))
        self.assertNotIn("super-secret", repr(row["input_json"]))
        self.assertIn("__secret_hash__", repr(row["input_json"]))

    async def test_different_secrets_produce_different_fingerprints(self) -> None:
        first = await self.cl.compute.run(
            name="call_api",
            inputs={"token": self.cl.secret("a")},
            fn=lambda: {"ok": 1},
        )
        second = await self.cl.compute.run(
            name="call_api",
            inputs={"token": self.cl.secret("b")},
            fn=lambda: {"ok": 2},
        )
        self.assertNotEqual(first.fingerprint, second.fingerprint)


class ResourceTests(ComputeRunTestCase):
    """§33."""

    async def test_upsert_reports_change(self) -> None:
        first = await self.cl.upsert_resource("company:NVDA:financials", "sha256:abc")
        self.assertTrue(first["changed"])
        self.assertIsNone(first["previous_version"])

        same = await self.cl.upsert_resource("company:NVDA:financials", "sha256:abc")
        self.assertFalse(same["changed"])

        changed = await self.cl.upsert_resource("company:NVDA:financials", "sha256:def")
        self.assertTrue(changed["changed"])
        self.assertEqual(changed["previous_version"], "sha256:abc")

    async def test_content_is_hashed_when_no_version_given(self) -> None:
        result = await self.cl.upsert_resource(
            "company:NVDA:news", content=[{"headline": "chips"}]
        )
        self.assertTrue(result["current_version"].startswith("sha256:"))


class ExplainTests(ComputeRunTestCase):
    """§53."""

    async def test_explain_names_the_dependency_that_changed(self) -> None:
        async def call(version: str):
            return await self.cl.compute.run(
                name="financial_analysis",
                inputs={"ticker": "NVDA"},
                dependencies=[self.cl.dep("financials:NVDA", version=version)],
                fn=lambda: {"a": 1},
            )

        await call("943fa1")
        second = await call("03ec22")

        explanation = await self.cl.explain(second.computation_id)
        self.assertEqual(explanation["cache_status"], CacheStatus.STALE)
        self.assertEqual(
            explanation["changes"],
            [
                {
                    "kind": "dependency_changed",
                    "key": "financials:NVDA",
                    "old": "943fa1",
                    "new": "03ec22",
                }
            ],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class FrozenClock:
    """A clock that never advances, so every row shares a timestamp."""

    def __init__(self) -> None:
        self.now = _dt.datetime(2026, 8, 25, 12, 0, 0, tzinfo=_dt.timezone.utc)

    def __call__(self) -> _dt.datetime:
        return self.now


class NewestWinsTests(unittest.IsolatedAsyncioTestCase):
    """§21: the latest valid computation wins, even when timestamps tie.

    ``created_at`` defaults to ``now()`` in PostgreSQL, which is *transaction*
    time -- two rows written in one transaction carry an identical value. With
    a plain ``ORDER BY created_at DESC LIMIT 1`` the sort is unstable, and the
    database returned the *older* row on every attempt. The API resolves this
    with a monotonic ``seq`` column; the reference backend uses its insertion
    counter. This test pins the invariant in both.
    """

    async def asyncSetUp(self) -> None:
        self.backend = LocalBackend(clock=FrozenClock())
        self.cl = ComputeLayer(project="tests", transport=self.backend)

    async def test_forced_result_wins_against_a_tied_timestamp(self) -> None:
        counter = Counter()

        async def call(force: bool = False):
            return await self.cl.compute.run(
                name="latest_news",
                inputs={"ticker": "NVDA"},
                force=force,
                fn=lambda: {"generation": counter.bump()},
            )

        await call()
        await call(force=True)

        timestamps = {row["created_at"] for row in self.backend.computations.values()}
        self.assertEqual(len(timestamps), 1, "the clock must not have advanced")

        reused = await call()
        self.assertEqual(reused.cache_status, CacheStatus.HIT)
        self.assertEqual(
            reused.value,
            {"generation": 2},
            "reuse must resolve to the newest result, not whichever row sorts first",
        )
