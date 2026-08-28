"""The API and the SDK must agree on what a fingerprint is.

The API stores fingerprints the SDK computes and never recomputes them, so a
divergence would be silent. This test pins the contract by importing the same
functions the SDK uses and checking the shapes the API's columns expect.
"""

from __future__ import annotations

from computelayer import (
    build_fingerprint,
    build_logical_key,
    build_model_agnostic_fingerprint,
    sha256_json,
)


def test_fingerprints_are_64_hex_characters() -> None:
    fingerprint = build_fingerprint(name="x", inputs={"a": 1})
    assert len(fingerprint) == 64
    assert set(fingerprint) <= set("0123456789abcdef")


def test_logical_keys_are_64_hex_characters() -> None:
    logical_key = build_logical_key(name="x", inputs={"a": 1})
    assert len(logical_key) == 64
    assert set(logical_key) <= set("0123456789abcdef")


def test_model_agnostic_fingerprints_are_64_hex_characters() -> None:
    # Pins the same shape ck_computations_model_agnostic_fingerprint_hex
    # enforces on the `computations` table (migration 0002).
    fingerprint = build_model_agnostic_fingerprint(name="x", inputs={"a": 1})
    assert len(fingerprint) == 64
    assert set(fingerprint) <= set("0123456789abcdef")


def test_output_hashes_are_64_hex_characters() -> None:
    assert len(sha256_json({"revenue": 100})) == 64
