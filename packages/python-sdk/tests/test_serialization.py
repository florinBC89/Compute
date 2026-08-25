"""Canonical serialization and hash stability (spec §13, §14, §50, §51)."""

from __future__ import annotations

import datetime as _dt
import decimal
import unittest
import uuid
from dataclasses import dataclass

from computelayer import canonical_json, normalize, secret, sha256_json
from computelayer.result import ComputeResult
from computelayer.serialization import CanonicalizationError, RefMode


class DictionaryOrderingTests(unittest.TestCase):
    """§51: these must produce equal fingerprints."""

    def test_key_order_does_not_change_the_hash(self) -> None:
        self.assertEqual(sha256_json({"a": 1, "b": 2}), sha256_json({"b": 2, "a": 1}))

    def test_nested_key_order_does_not_change_the_hash(self) -> None:
        left = {"outer": {"a": 1, "b": {"x": 1, "y": 2}}, "z": [1, 2]}
        right = {"z": [1, 2], "outer": {"b": {"y": 2, "x": 1}, "a": 1}}
        self.assertEqual(sha256_json(left), sha256_json(right))

    def test_whitespace_is_never_emitted(self) -> None:
        self.assertEqual(canonical_json({"a": 1, "b": [1, 2]}), '{"a":1,"b":[1,2]}')


class OrderingRulesTests(unittest.TestCase):
    def test_list_order_is_preserved(self) -> None:
        self.assertNotEqual(sha256_json([1, 2, 3]), sha256_json([3, 2, 1]))

    def test_sets_are_sorted(self) -> None:
        self.assertEqual(sha256_json({3, 1, 2}), sha256_json({2, 3, 1}))

    def test_set_of_mixed_types_is_stable(self) -> None:
        # Deliberately avoids {1, True}: Python collapses those into a single
        # element and keeps whichever was inserted first, so such a set is
        # already non-deterministic before canonicalization sees it.
        self.assertEqual(
            sha256_json({1, "a", 2.5, None}), sha256_json({None, 2.5, "a", 1})
        )

    def test_tuple_and_list_agree(self) -> None:
        self.assertEqual(sha256_json((1, 2)), sha256_json([1, 2]))


class ScalarNormalizationTests(unittest.TestCase):
    def test_datetime_becomes_utc_iso8601(self) -> None:
        moment = _dt.datetime(2026, 8, 25, 12, 0, 0, tzinfo=_dt.timezone.utc)
        self.assertEqual(normalize(moment), "2026-08-25T12:00:00.000000Z")

    def test_naive_datetime_is_treated_as_utc(self) -> None:
        naive = _dt.datetime(2026, 8, 25, 12, 0, 0)
        aware = _dt.datetime(2026, 8, 25, 12, 0, 0, tzinfo=_dt.timezone.utc)
        self.assertEqual(normalize(naive), normalize(aware))

    def test_equivalent_instants_in_different_zones_agree(self) -> None:
        east = _dt.datetime(
            2026, 8, 25, 15, 0, 0, tzinfo=_dt.timezone(_dt.timedelta(hours=3))
        )
        utc = _dt.datetime(2026, 8, 25, 12, 0, 0, tzinfo=_dt.timezone.utc)
        self.assertEqual(sha256_json(east), sha256_json(utc))

    def test_uuid_is_lowercased(self) -> None:
        value = uuid.UUID("A1B2C3D4-0000-0000-0000-000000000000")
        self.assertEqual(normalize(value), "a1b2c3d4-0000-0000-0000-000000000000")

    def test_negative_zero_matches_zero(self) -> None:
        self.assertEqual(sha256_json(-0.0), sha256_json(0.0))

    def test_non_finite_floats_are_rejected(self) -> None:
        with self.assertRaises(CanonicalizationError):
            canonical_json(float("nan"))
        with self.assertRaises(CanonicalizationError):
            canonical_json(float("inf"))

    def test_decimal_is_tagged_and_trailing_zeros_normalized(self) -> None:
        self.assertEqual(
            sha256_json(decimal.Decimal("1.10")), sha256_json(decimal.Decimal("1.1"))
        )
        self.assertNotEqual(sha256_json(decimal.Decimal("1.1")), sha256_json("1.1"))

    def test_bytes_round_trip_as_base64(self) -> None:
        self.assertEqual(normalize(b"hi"), {"__bytes__": "aGk="})

    def test_unsupported_type_raises(self) -> None:
        with self.assertRaises(CanonicalizationError):
            canonical_json(object())

    def test_circular_reference_raises(self) -> None:
        loop: dict = {}
        loop["self"] = loop
        with self.assertRaises(CanonicalizationError):
            canonical_json(loop)


class StructuredObjectTests(unittest.TestCase):
    def test_dataclass_serializes_like_its_dict(self) -> None:
        @dataclass
        class Point:
            x: int
            y: int

        self.assertEqual(sha256_json(Point(1, 2)), sha256_json({"x": 1, "y": 2}))

    def test_dataclasses_are_recursed(self) -> None:
        @dataclass
        class Inner:
            a: int

        @dataclass
        class Outer:
            inner: Inner

        self.assertEqual(sha256_json(Outer(Inner(1))), sha256_json({"inner": {"a": 1}}))


class SecretTests(unittest.TestCase):
    """§57: secrets hash but are never stored in plaintext."""

    def test_secret_never_appears_in_canonical_output(self) -> None:
        rendered = canonical_json({"api_token": secret("hunter2")})
        self.assertNotIn("hunter2", rendered)
        self.assertIn("__secret_hash__", rendered)

    def test_secret_is_stable(self) -> None:
        self.assertEqual(sha256_json(secret("a")), sha256_json(secret("a")))

    def test_different_secrets_differ(self) -> None:
        self.assertNotEqual(sha256_json(secret("a")), sha256_json(secret("b")))

    def test_repr_is_redacted(self) -> None:
        self.assertNotIn("hunter2", repr(secret("hunter2")))
        self.assertNotIn("hunter2", f"{secret('hunter2')}")


class ComputeRefTests(unittest.TestCase):
    """§13, with the computation_id correction documented in serialization.py."""

    def _result(self, **overrides) -> ComputeResult:
        defaults = dict(
            value={"ok": True},
            computation_id="11111111-1111-1111-1111-111111111111",
            cache_status="MISS",
            fingerprint="f" * 64,
            output_hash="a" * 64,
            logical_key="b" * 64,
            name="financials",
        )
        defaults.update(overrides)
        return ComputeResult(**defaults)

    def test_version_mode_exposes_only_the_output_hash(self) -> None:
        ref = normalize(self._result(), RefMode.VERSION)
        self.assertEqual(ref, {"__compute_ref__": True, "output_hash": "a" * 64})

    def test_identity_mode_exposes_only_the_logical_key(self) -> None:
        ref = normalize(self._result(), RefMode.IDENTITY)
        self.assertEqual(ref, {"__compute_ref__": True, "logical_key": "b" * 64})

    def test_computation_id_does_not_affect_the_hashed_forms(self) -> None:
        first = self._result(computation_id="id-one")
        second = self._result(computation_id="id-two")
        self.assertEqual(
            sha256_json({"upstream": first}), sha256_json({"upstream": second})
        )

    def test_provenance_mode_keeps_the_computation_id(self) -> None:
        ref = normalize(self._result(), RefMode.PROVENANCE)
        self.assertEqual(ref["computation_id"], "11111111-1111-1111-1111-111111111111")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
