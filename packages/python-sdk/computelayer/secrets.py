"""Sensitive-input handling (spec §57).

A :class:`Secret` contributes to the fingerprint through its SHA-256 digest but
is never serialized in plaintext -- not into ``input_json``, not into logs, and
not into tracebacks.
"""

from __future__ import annotations

import hashlib
from typing import Any

__all__ = ["Secret", "secret"]


class Secret:
    """Wraps a value so it participates in hashing but is never stored."""

    __slots__ = ("_digest", "_value")

    def __init__(self, value: Any) -> None:
        from computelayer.serialization import canonical_json

        # Strings hash as their raw bytes so cl.secret("t") is stable regardless
        # of JSON quoting; everything else goes through canonical JSON.
        if isinstance(value, str):
            payload = value.encode("utf-8")
        elif isinstance(value, (bytes, bytearray)):
            payload = bytes(value)
        else:
            payload = canonical_json(value).encode("utf-8")

        self._digest = hashlib.sha256(payload).hexdigest()
        self._value = value

    @property
    def digest(self) -> str:
        """Hex SHA-256 of the wrapped value."""
        return self._digest

    def reveal(self) -> Any:
        """Return the underlying value. Only call this inside your own code."""
        return self._value

    def canonical(self) -> dict[str, str]:
        return {"__secret_hash__": f"sha256:{self._digest}"}

    # Every rendering path is redacted, including f-strings and tracebacks.
    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"Secret(sha256:{self._digest[:12]}...)"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and other._digest == self._digest

    def __hash__(self) -> int:
        return hash(("computelayer.Secret", self._digest))


def secret(value: Any) -> Secret:
    """Convenience constructor, also exposed as ``cl.secret``."""
    return Secret(value)
