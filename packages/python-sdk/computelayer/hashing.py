"""Hashing, fingerprints and logical keys (spec §14, §15, §16, §22, §23, §24)."""

from __future__ import annotations

import hashlib
import os
from typing import Any, Iterable, Sequence

from computelayer.dependency import Dependency
from computelayer.errors import DuplicateDependencyError
from computelayer.serialization import (
    SPEC_VERSION,
    RefMode,
    canonical_json,
    normalize,
)

__all__ = [
    "sha256_hex",
    "sha256_json",
    "hash_text",
    "hash_json",
    "build_fingerprint",
    "build_model_agnostic_fingerprint",
    "build_logical_key",
    "get_code_version",
    "dedupe_dependencies",
    "CODE_VERSION_ENV",
    "UNKNOWN_CODE_VERSION",
]

CODE_VERSION_ENV = "COMPUTELAYER_CODE_VERSION"
UNKNOWN_CODE_VERSION = "unknown"


# --------------------------------------------------------------------------
# §14 hash algorithm
# --------------------------------------------------------------------------


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any, ref_mode: RefMode = RefMode.VERSION) -> str:
    return sha256_hex(canonical_json(value, ref_mode))


def hash_text(text: str | None) -> str | None:
    """SHA-256 of a prompt, or ``None`` when no prompt was supplied (§23)."""
    if text is None:
        return None
    return sha256_hex(text)


def hash_json(value: Any | None) -> str | None:
    """SHA-256 of normalized tool schemas, or ``None`` when absent (§24)."""
    if value is None:
        return None
    return sha256_json(value)


# --------------------------------------------------------------------------
# §22 code version
# --------------------------------------------------------------------------


def get_code_version(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    return os.getenv(CODE_VERSION_ENV) or UNKNOWN_CODE_VERSION


# --------------------------------------------------------------------------
# dependencies
# --------------------------------------------------------------------------


def dedupe_dependencies(dependencies: Iterable[Dependency]) -> list[Dependency]:
    """Collapse identical dependencies; reject conflicting ones.

    ``computation_dependencies`` is unique on ``(computation_id,
    dependency_key)``.  Two declarations of the same key with different
    versions are ambiguous, and guessing which one wins is exactly the kind of
    thing that produces incorrect reuse -- so it is an error.
    """
    by_key: dict[str, Dependency] = {}
    for dependency in dependencies:
        existing = by_key.get(dependency.key)
        if existing is None:
            by_key[dependency.key] = dependency
            continue
        if existing.version != dependency.version or existing.type != dependency.type:
            raise DuplicateDependencyError(
                f"dependency {dependency.key!r} declared twice with different "
                f"versions ({existing.version!r} vs {dependency.version!r})"
            )
        # Identical declaration; keep whichever carries provenance.
        if existing.source_computation_id is None:
            by_key[dependency.key] = dependency
    return sorted(by_key.values(), key=lambda item: item.key)


def _dependency_payload(dependencies: Sequence[Dependency]) -> list[dict[str, str]]:
    return [
        {
            "key": dependency.key,
            "version": dependency.version,
            "type": dependency.type,
        }
        for dependency in dedupe_dependencies(dependencies)
    ]


# --------------------------------------------------------------------------
# §15 fingerprint
# --------------------------------------------------------------------------


def build_fingerprint(
    *,
    name: str,
    inputs: Any,
    dependencies: Sequence[Dependency] = (),
    model: str | None = None,
    prompt_hash: str | None = None,
    tool_schema_hash: str | None = None,
    code_version: str | None = None,
) -> str:
    """Answer: *is this exact computation reusable?*

    Embedded :class:`ComputeResult` inputs are reduced to their ``output_hash``
    (``RefMode.VERSION``) so that an upstream re-execution which produces an
    identical output leaves this fingerprint untouched -- the propagation
    behaviour required by §19.
    """
    payload = {
        "spec_version": SPEC_VERSION,
        "name": name,
        "inputs": normalize(inputs, RefMode.VERSION),
        "dependencies": _dependency_payload(dependencies),
        "execution": {
            "model": model,
            "prompt_hash": prompt_hash,
            "tool_schema_hash": tool_schema_hash,
            "code_version": get_code_version(code_version),
        },
    }
    return sha256_hex(canonical_json(payload))


def build_model_agnostic_fingerprint(
    *,
    name: str,
    inputs: Any,
    dependencies: Sequence[Dependency] = (),
    prompt_hash: str | None = None,
    tool_schema_hash: str | None = None,
    code_version: str | None = None,
) -> str:
    """Answer: *is this exact computation reusable, ignoring which model ran it?*

    Identical to :func:`build_fingerprint` except ``model`` is never included
    in the hashed payload. Used by cross-model reuse (V0.2): two computations
    with the same inputs and dependencies but different models produce the
    same value here, so equality is a cheap way to confirm nothing except the
    model changed -- including catching a dependency change that a bare
    field-by-field comparison of execution parameters would miss.
    """
    return build_fingerprint(
        name=name,
        inputs=inputs,
        dependencies=dependencies,
        model=None,
        prompt_hash=prompt_hash,
        tool_schema_hash=tool_schema_hash,
        code_version=code_version,
    )


# --------------------------------------------------------------------------
# §16 logical key
# --------------------------------------------------------------------------


def build_logical_key(*, name: str, inputs: Any) -> str:
    """Answer: *is there an older version of this same logical computation?*

    Embedded results reduce to the upstream ``logical_key``
    (``RefMode.IDENTITY``), which is stable across upstream re-executions.  A
    changed upstream therefore resolves to ``STALE`` rather than ``MISS``.

    V0.1 uses all normalized inputs as identity inputs.
    """
    payload = {
        "spec_version": SPEC_VERSION,
        "name": name,
        "identity_inputs": normalize(inputs, RefMode.IDENTITY),
    }
    return sha256_hex(canonical_json(payload))
