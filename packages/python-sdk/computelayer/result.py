"""ComputeResult (spec §9) and cache-status constants (spec §3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Literal

from computelayer.serialization import RefMode

__all__ = ["ComputeResult", "CacheStatus", "ComputationStatus", "CACHE_STATUSES"]

CacheStatusLiteral = Literal["HIT", "MISS", "STALE", "FORCED"]


class CacheStatus:
    """Execution states (§3). ``FAILED`` lives on ``status``, not ``cache_status``."""

    HIT: Final = "HIT"
    MISS: Final = "MISS"
    STALE: Final = "STALE"
    FORCED: Final = "FORCED"


CACHE_STATUSES: Final[frozenset[str]] = frozenset(
    {CacheStatus.HIT, CacheStatus.MISS, CacheStatus.STALE, CacheStatus.FORCED}
)


class ComputationStatus:
    RUNNING: Final = "RUNNING"
    SUCCEEDED: Final = "SUCCEEDED"
    FAILED: Final = "FAILED"


@dataclass
class ComputeResult:
    """What ``compute.run`` hands back. Developers normally read ``.value``."""

    value: Any
    computation_id: str
    cache_status: CacheStatusLiteral
    fingerprint: str
    output_hash: str
    logical_key: str = ""
    name: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    saved_usd: float = 0.0
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def reused(self) -> bool:
        return self.cache_status == CacheStatus.HIT

    @property
    def executed(self) -> bool:
        return self.cache_status != CacheStatus.HIT

    def canonical_ref(self, ref_mode: RefMode = RefMode.VERSION) -> dict[str, Any]:
        """Compact reference used when this result is nested inside inputs (§13).

        ``computation_id`` appears only in ``RefMode.PROVENANCE``; including a
        per-run UUID in a hashed form would defeat reuse entirely.
        """
        if ref_mode is RefMode.IDENTITY:
            return {"__compute_ref__": True, "logical_key": self.logical_key}
        if ref_mode is RefMode.PROVENANCE:
            return {
                "__compute_ref__": True,
                "name": self.name,
                "logical_key": self.logical_key,
                "output_hash": self.output_hash,
                "computation_id": self.computation_id,
            }
        return {"__compute_ref__": True, "output_hash": self.output_hash}
