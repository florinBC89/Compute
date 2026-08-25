"""Dependency objects (spec §11, §6.5)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Final

__all__ = ["Dependency", "DependencyType", "dep", "DEPENDENCY_TYPES"]


class DependencyType:
    """Allowed ``dependency_type`` values (§6.5)."""

    EXTERNAL: Final = "EXTERNAL"
    COMPUTATION: Final = "COMPUTATION"
    FILE: Final = "FILE"
    API: Final = "API"
    DATABASE: Final = "DATABASE"
    MANUAL: Final = "MANUAL"


DEPENDENCY_TYPES: Final[frozenset[str]] = frozenset(
    {
        DependencyType.EXTERNAL,
        DependencyType.COMPUTATION,
        DependencyType.FILE,
        DependencyType.API,
        DependencyType.DATABASE,
        DependencyType.MANUAL,
    }
)


@dataclass(frozen=True)
class Dependency:
    """A versioned thing a computation depends on."""

    key: str
    version: str
    type: str = DependencyType.MANUAL
    source_computation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("dependency key must be a non-empty string")
        if not self.version:
            raise ValueError(
                f"dependency {self.key!r} needs a version; pass version=... or content=..."
            )
        if self.type not in DEPENDENCY_TYPES:
            raise ValueError(
                f"unknown dependency type {self.type!r}; "
                f"expected one of {sorted(DEPENDENCY_TYPES)}"
            )

    def as_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "version": self.version,
            "type": self.type,
            "source_computation_id": self.source_computation_id,
        }


def dep(
    key: str,
    version: str | None = None,
    *,
    content: Any = None,
    type: str = DependencyType.MANUAL,
    source_computation_id: str | None = None,
) -> Dependency:
    """Build a :class:`Dependency`, hashing ``content`` when no version is given.

    ::

        cl.dep("financials:NVDA", version="sha256:1234")
        cl.dep("financials:NVDA", content=financials)
    """
    if version is None and content is None:
        raise ValueError(
            f"dependency {key!r} requires either version=... or content=..."
        )
    if version is not None and content is not None:
        raise ValueError(
            f"dependency {key!r} got both version=... and content=...; pass one"
        )

    if version is None:
        from computelayer.serialization import canonical_json

        digest = hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()
        version = f"sha256:{digest}"

    return Dependency(
        key=key,
        version=version,
        type=type,
        source_computation_id=source_computation_id,
    )
