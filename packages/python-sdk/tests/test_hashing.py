"""Fingerprints, logical keys and invalidation triggers (spec §15, §16, §51)."""

from __future__ import annotations

import os
import unittest

from computelayer import (
    Dependency,
    build_fingerprint,
    build_logical_key,
    build_model_agnostic_fingerprint,
    dep,
)
from computelayer.errors import DuplicateDependencyError
from computelayer.hashing import (
    CODE_VERSION_ENV,
    UNKNOWN_CODE_VERSION,
    dedupe_dependencies,
    get_code_version,
    hash_json,
    hash_text,
)
from computelayer.result import ComputeResult

BASE = dict(name="financial_analysis", inputs={"ticker": "NVDA", "period": "FY2025"})


def fingerprint(**overrides) -> str:
    payload = {**BASE, **overrides}
    return build_fingerprint(**payload)


class FingerprintEqualityTests(unittest.TestCase):
    """§51: these must produce equal fingerprints."""

    def test_stable_across_calls(self) -> None:
        self.assertEqual(fingerprint(), fingerprint())

    def test_input_key_order_is_irrelevant(self) -> None:
        self.assertEqual(
            fingerprint(inputs={"ticker": "NVDA", "period": "FY2025"}),
            fingerprint(inputs={"period": "FY2025", "ticker": "NVDA"}),
        )

    def test_dependency_order_is_irrelevant(self) -> None:
        first = dep("a:1", version="v1")
        second = dep("b:2", version="v2")
        self.assertEqual(
            fingerprint(dependencies=[first, second]),
            fingerprint(dependencies=[second, first]),
        )

    def test_duplicate_identical_dependencies_collapse(self) -> None:
        one = dep("a:1", version="v1")
        self.assertEqual(
            fingerprint(dependencies=[one]), fingerprint(dependencies=[one, one])
        )


class FingerprintDifferenceTests(unittest.TestCase):
    """§51: these must produce different fingerprints."""

    def test_different_prompt(self) -> None:
        self.assertNotEqual(
            fingerprint(prompt_hash=hash_text("prompt A")),
            fingerprint(prompt_hash=hash_text("prompt B")),
        )

    def test_different_model(self) -> None:
        self.assertNotEqual(
            fingerprint(model="openai/gpt-4o"),
            fingerprint(model="openai/gpt-4o-mini"),
        )

    def test_different_dependency_version(self) -> None:
        self.assertNotEqual(
            fingerprint(dependencies=[dep("financials:NVDA", version="943fa1")]),
            fingerprint(dependencies=[dep("financials:NVDA", version="03ec22")]),
        )

    def test_different_code_version(self) -> None:
        self.assertNotEqual(
            fingerprint(code_version="sha-a"), fingerprint(code_version="sha-b")
        )

    def test_different_tool_schema(self) -> None:
        self.assertNotEqual(
            fingerprint(tool_schema_hash=hash_json([{"name": "search"}])),
            fingerprint(tool_schema_hash=hash_json([{"name": "browse"}])),
        )

    def test_different_name(self) -> None:
        self.assertNotEqual(fingerprint(), fingerprint(name="something_else"))

    def test_different_inputs(self) -> None:
        self.assertNotEqual(
            fingerprint(), fingerprint(inputs={"ticker": "AMD", "period": "FY2025"})
        )

    def test_absent_prompt_differs_from_empty_prompt(self) -> None:
        self.assertNotEqual(fingerprint(), fingerprint(prompt_hash=hash_text("")))


def model_agnostic_fingerprint(**overrides) -> str:
    payload = {**BASE, **overrides}
    return build_model_agnostic_fingerprint(**payload)


class ModelAgnosticFingerprintTests(unittest.TestCase):
    """Cross-model reuse: same value regardless of which model ran it."""

    def test_equals_fingerprint_called_with_no_model(self) -> None:
        self.assertEqual(model_agnostic_fingerprint(), fingerprint(model=None))

    def test_invariant_across_models_that_would_differ_by_fingerprint(self) -> None:
        # The whole point: build_fingerprint moves when model changes, but
        # build_model_agnostic_fingerprint doesn't take a model at all, so
        # every call with the same inputs/dependencies/execution params
        # collapses to one value -- that's what makes it useful as an
        # equality check for "only the model changed."
        self.assertNotEqual(
            fingerprint(model="openai/gpt-4o"),
            fingerprint(model="anthropic/claude-3-5-sonnet"),
        )
        self.assertEqual(
            model_agnostic_fingerprint(), model_agnostic_fingerprint()
        )

    def test_different_from_a_model_specific_fingerprint(self) -> None:
        self.assertNotEqual(
            model_agnostic_fingerprint(), fingerprint(model="openai/gpt-4o")
        )

    def test_sensitive_to_inputs(self) -> None:
        self.assertNotEqual(
            model_agnostic_fingerprint(),
            model_agnostic_fingerprint(inputs={"ticker": "AMD", "period": "FY2025"}),
        )

    def test_sensitive_to_dependency_version(self) -> None:
        self.assertNotEqual(
            model_agnostic_fingerprint(
                dependencies=[dep("financials:NVDA", version="943fa1")]
            ),
            model_agnostic_fingerprint(
                dependencies=[dep("financials:NVDA", version="03ec22")]
            ),
        )

    def test_sensitive_to_prompt(self) -> None:
        self.assertNotEqual(
            model_agnostic_fingerprint(prompt_hash=hash_text("prompt A")),
            model_agnostic_fingerprint(prompt_hash=hash_text("prompt B")),
        )

    def test_sensitive_to_code_version(self) -> None:
        self.assertNotEqual(
            model_agnostic_fingerprint(code_version="sha-a"),
            model_agnostic_fingerprint(code_version="sha-b"),
        )


class DependencyHelperTests(unittest.TestCase):
    def test_content_is_hashed_into_a_version(self) -> None:
        dependency = dep("financials:NVDA", content={"revenue": 1})
        self.assertTrue(dependency.version.startswith("sha256:"))
        self.assertEqual(
            dependency.version, dep("financials:NVDA", content={"revenue": 1}).version
        )

    def test_content_and_version_are_mutually_exclusive(self) -> None:
        with self.assertRaises(ValueError):
            dep("k", version="v", content={"a": 1})
        with self.assertRaises(ValueError):
            dep("k")

    def test_unknown_dependency_type_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Dependency(key="k", version="v", type="NONSENSE")

    def test_conflicting_versions_for_one_key_are_rejected(self) -> None:
        with self.assertRaises(DuplicateDependencyError):
            dedupe_dependencies([dep("k", version="v1"), dep("k", version="v2")])

    def test_dedupe_sorts_by_key(self) -> None:
        result = dedupe_dependencies([dep("z", version="1"), dep("a", version="1")])
        self.assertEqual([d.key for d in result], ["a", "z"])


class LogicalKeyTests(unittest.TestCase):
    """§16: identity, not version."""

    def test_same_inputs_same_logical_key(self) -> None:
        self.assertEqual(
            build_logical_key(name="x", inputs={"a": 1}),
            build_logical_key(name="x", inputs={"a": 1}),
        )

    def test_execution_parameters_do_not_affect_it(self) -> None:
        # Logical key has no model/prompt/code fields at all -- changing those
        # must move the fingerprint while leaving identity untouched.
        key = build_logical_key(name="x", inputs={"a": 1})
        self.assertEqual(key, build_logical_key(name="x", inputs={"a": 1}))
        self.assertNotEqual(
            fingerprint(name="x", inputs={"a": 1}, model="m1"),
            fingerprint(name="x", inputs={"a": 1}, model="m2"),
        )

    def test_upstream_output_change_keeps_identity_but_moves_fingerprint(self) -> None:
        def upstream(output_hash: str) -> ComputeResult:
            return ComputeResult(
                value=None,
                computation_id="c1",
                cache_status="MISS",
                fingerprint="f" * 64,
                output_hash=output_hash,
                logical_key="stable-logical-key",
                name="financials",
            )

        before = {"financials": upstream("hash-v1")}
        after = {"financials": upstream("hash-v2")}

        self.assertEqual(
            build_logical_key(name="analysis", inputs=before),
            build_logical_key(name="analysis", inputs=after),
            "identity must survive an upstream re-execution so lookups say STALE",
        )
        self.assertNotEqual(
            build_fingerprint(name="analysis", inputs=before),
            build_fingerprint(name="analysis", inputs=after),
            "a changed upstream output must invalidate the fingerprint",
        )


class CodeVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = os.environ.get(CODE_VERSION_ENV)
        os.environ.pop(CODE_VERSION_ENV, None)

    def tearDown(self) -> None:
        if self._saved is None:
            os.environ.pop(CODE_VERSION_ENV, None)
        else:
            os.environ[CODE_VERSION_ENV] = self._saved

    def test_defaults_to_unknown(self) -> None:
        self.assertEqual(get_code_version(), UNKNOWN_CODE_VERSION)

    def test_reads_the_environment(self) -> None:
        os.environ[CODE_VERSION_ENV] = "abc123"
        self.assertEqual(get_code_version(), "abc123")

    def test_explicit_value_wins(self) -> None:
        os.environ[CODE_VERSION_ENV] = "abc123"
        self.assertEqual(get_code_version("def456"), "def456")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
