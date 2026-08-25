"""Canonical serialization (spec §13).

Fingerprints must never depend on dictionary ordering, whitespace, object
memory address, or Python ``repr`` formatting.  Every value that participates
in a fingerprint, a logical key, or an output hash passes through
:func:`normalize` first and is then rendered by :func:`canonical_json`.

Reference-mode
--------------
A :class:`~computelayer.result.ComputeResult` embedded in an input dict is
replaced by a compact reference.  *Which* reference depends on what the
canonical form is being used for:

``RefMode.VERSION``
    ``{"__compute_ref__": true, "output_hash": ...}`` -- used for the
    **fingerprint**.  Changes exactly when the upstream *output* changes,
    which is what makes output-hash propagation (§19) work.

``RefMode.IDENTITY``
    ``{"__compute_ref__": true, "logical_key": ...}`` -- used for the
    **logical key** (§16).  Stable across upstream re-executions so that a
    changed upstream yields ``STALE`` rather than ``MISS``.

``RefMode.PROVENANCE``
    Full reference including ``computation_id`` -- used only for the
    ``input_json`` column, never for hashing.

.. note::
   Spec §13 shows ``computation_id`` inside ``__compute_ref__``.  Including a
   per-run UUID in the fingerprint would make every downstream computation a
   permanent ``MISS``, so ``computation_id`` is deliberately excluded from the
   hashed forms and carried instead by
   ``computation_dependencies.source_computation_id`` (§6.5, §12).
"""

from __future__ import annotations

import base64
import dataclasses
import datetime as _dt
import decimal
import enum
import json
import math
import pathlib
import uuid
from typing import Any

__all__ = [
    "RefMode",
    "CanonicalizationError",
    "normalize",
    "canonical_json",
    "SPEC_VERSION",
]

SPEC_VERSION = "computelayer-v0.1"


class RefMode(str, enum.Enum):
    """How an embedded :class:`ComputeResult` is rendered."""

    VERSION = "version"
    IDENTITY = "identity"
    PROVENANCE = "provenance"


class CanonicalizationError(TypeError):
    """A value cannot be canonicalized deterministically."""


# --------------------------------------------------------------------------
# scalars
# --------------------------------------------------------------------------


def _normalize_float(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        raise CanonicalizationError(
            f"non-finite float {value!r} cannot be canonicalized; "
            "NaN and Infinity have no canonical JSON representation"
        )
    # -0.0 and 0.0 are numerically equal but render differently.
    if value == 0.0:
        return 0.0
    return value


def _normalize_datetime(value: _dt.datetime) -> str:
    """UTC ISO-8601 with microsecond precision, e.g. ``2026-08-25T12:00:00.000000Z``."""
    if value.tzinfo is None:
        aware = value.replace(tzinfo=_dt.timezone.utc)
    else:
        aware = value.astimezone(_dt.timezone.utc)
    return aware.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _normalize_key(key: Any) -> str:
    """Dictionary keys are coerced to a deterministic string form."""
    if isinstance(key, str):
        return key
    if isinstance(key, bool):
        return "true" if key else "false"
    if isinstance(key, int):
        return str(key)
    if isinstance(key, float):
        return repr(_normalize_float(key))
    if key is None:
        return "null"
    if isinstance(key, uuid.UUID):
        return str(key).lower()
    if isinstance(key, _dt.datetime):
        return _normalize_datetime(key)
    if isinstance(key, enum.Enum):
        return _normalize_key(key.value)
    raise CanonicalizationError(
        f"dictionary key of type {type(key).__name__!r} is not canonicalizable"
    )


# --------------------------------------------------------------------------
# normalize
# --------------------------------------------------------------------------


def normalize(value: Any, ref_mode: RefMode = RefMode.VERSION) -> Any:
    """Return a JSON-safe, deterministic representation of ``value``."""
    return _normalize(value, ref_mode, _seen=set())


def _normalize(value: Any, ref_mode: RefMode, _seen: set[int]) -> Any:
    # -- ComputeLayer sentinels ------------------------------------------
    #    imported lazily to keep this module free of internal cycles
    from computelayer.result import ComputeResult
    from computelayer.secrets import Secret

    if isinstance(value, Secret):
        return value.canonical()

    if isinstance(value, ComputeResult):
        return value.canonical_ref(ref_mode)

    # -- primitives -------------------------------------------------------
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):  # bool handled above
        return value
    if isinstance(value, float):
        return _normalize_float(value)

    # -- tagged scalars ---------------------------------------------------
    if isinstance(value, decimal.Decimal):
        if not value.is_finite():
            raise CanonicalizationError(f"non-finite Decimal {value!r}")
        normalized = value.normalize()
        # normalize() renders integral values in exponent form (1E+2); expand.
        return {"__decimal__": format(normalized, "f")}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"__bytes__": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, uuid.UUID):
        return str(value).lower()
    if isinstance(value, _dt.datetime):
        return _normalize_datetime(value)
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, _dt.time):
        return value.isoformat()
    if isinstance(value, pathlib.PurePath):
        return value.as_posix()
    if isinstance(value, enum.Enum):
        return _normalize(value.value, ref_mode, _seen)

    # -- cycle guard for containers --------------------------------------
    marker = id(value)
    if marker in _seen:
        raise CanonicalizationError("circular reference in computation inputs")
    _seen = _seen | {marker}

    # -- containers -------------------------------------------------------
    if isinstance(value, dict):
        items = {}
        for raw_key, raw_value in value.items():
            key = _normalize_key(raw_key)
            if key in items:
                raise CanonicalizationError(
                    f"dictionary keys collide after canonicalization: {key!r}"
                )
            items[key] = _normalize(raw_value, ref_mode, _seen)
        # Sorting happens in canonical_json via sort_keys, but sorting here too
        # keeps normalize() output directly comparable.
        return {k: items[k] for k in sorted(items)}

    if isinstance(value, (list, tuple)):
        return [_normalize(item, ref_mode, _seen) for item in value]

    if isinstance(value, (set, frozenset)):
        normalized = [_normalize(item, ref_mode, _seen) for item in value]
        # Sets are unordered: sort by the canonical rendering of each element
        # so the result is stable across mixed types and insertion orders.
        return sorted(normalized, key=lambda item: _dump(item))

    # -- structured objects ----------------------------------------------
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _normalize(dataclasses.asdict(value), ref_mode, _seen)

    # Pydantic v2 / v1, duck-typed so pydantic stays an optional dependency.
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _normalize(model_dump(mode="python"), ref_mode, _seen)
    if hasattr(value, "__fields__") and callable(getattr(value, "dict", None)):
        return _normalize(value.dict(), ref_mode, _seen)

    raise CanonicalizationError(
        f"cannot canonicalize value of type {type(value).__name__!r}. "
        "Convert it to a dict/dataclass/pydantic model, or wrap it with "
        "cl.secret(...) if it must not be stored."
    )


# --------------------------------------------------------------------------
# canonical_json
# --------------------------------------------------------------------------


def _dump(normalized: Any) -> str:
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_json(value: Any, ref_mode: RefMode = RefMode.VERSION) -> str:
    """Normalize ``value`` and render it as canonical JSON text."""
    return _dump(normalize(value, ref_mode))
