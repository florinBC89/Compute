"""In-process reference backend.

``LocalBackend`` implements the same protocol as :class:`HttpTransport` against
plain Python dictionaries.  It has three jobs:

1. let the SDK's own test-suite exercise the real ``compute.run`` code path
   without Postgres, Redis or a network;
2. give developers an offline mode (``ComputeLayer(local=True)``);
3. serve as the executable specification the PostgreSQL implementation in
   ``apps/api`` is checked against.

Reuse decisions are delegated to :mod:`computelayer.semantics`, which the API
also imports, so the two backends cannot disagree about HIT/MISS/STALE.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import uuid
from typing import Any

from computelayer.result import CacheStatus, ComputationStatus
from computelayer.semantics import (
    DEFAULT_PORTABLE_ARTIFACT_TYPES,
    LookupRequest,
    StoredComputation,
    classify,
    upgrade_for_cross_model,
    utcnow,
)

__all__ = ["LocalBackend"]


def _new_id() -> str:
    return str(uuid.uuid4())


def _iso(value: _dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


class LocalBackend:
    """A complete ComputeLayer backend held in memory."""

    def __init__(self, *, project: str = "local", clock: Any = None) -> None:
        self.project = project
        self._clock = clock or utcnow

        self.computations: dict[str, dict[str, Any]] = {}
        self.dependencies: dict[str, list[dict[str, Any]]] = {}
        self.events: list[dict[str, Any]] = []
        self.resources: dict[str, dict[str, Any]] = {}
        self.runs: dict[str, dict[str, Any]] = {}

        self._locks: dict[str, asyncio.Lock] = {}

    # -- helpers ----------------------------------------------------------

    def now(self) -> _dt.datetime:
        return self._clock()

    def _event(self, computation_id: str, event_type: str, **payload: Any) -> None:
        self.events.append(
            {
                "computation_id": computation_id,
                "event_type": event_type,
                "payload": payload,
                "created_at": self.now(),
            }
        )

    def _stored(self, row: dict[str, Any]) -> StoredComputation:
        return StoredComputation(
            id=row["id"],
            name=row["name"],
            logical_key=row["logical_key"],
            fingerprint=row["fingerprint"],
            status=row["status"],
            output_json=row.get("output_json"),
            output_hash=row.get("output_hash"),
            cost_usd=row.get("cost_usd", 0.0),
            input_tokens=row.get("input_tokens", 0),
            output_tokens=row.get("output_tokens", 0),
            latency_ms=row.get("latency_ms"),
            reusable=row.get("reusable", True),
            expires_at=row.get("expires_at"),
            created_at=row["created_at"],
            model=row.get("model"),
            artifact_type=row.get("artifact_type"),
            model_agnostic_fingerprint=row.get("model_agnostic_fingerprint"),
        )

    def _rows_newest_first(self) -> list[dict[str, Any]]:
        return sorted(
            self.computations.values(),
            key=lambda row: (row["created_at"], row["_seq"]),
            reverse=True,
        )

    def _find_exact(self, fingerprint: str) -> StoredComputation | None:
        for row in self._rows_newest_first():
            if (
                row["fingerprint"] == fingerprint
                and row["status"] == ComputationStatus.SUCCEEDED
                and row.get("reusable", True)
            ):
                return self._stored(row)
        return None

    def _find_previous(self, logical_key: str) -> StoredComputation | None:
        # cache_status != HIT excludes observation rows (inserted below, in
        # lookup()): they record that a reuse *happened* but carry no output
        # of their own and no artifact_type/model_agnostic_fingerprint. Real
        # bug, found via a real second-then-third cross-model switch against
        # the Postgres-backed API (apps/api/app/services/lookup.py's
        # find_previous had the identical gap): once one HIT observation
        # existed for a logical key, it -- being the newest row -- shadowed
        # the real classified computation underneath it, so a *subsequent*
        # lookup or model-switch-preview for that key saw "not classified"
        # and refused to reuse or preview a switch that a portable source
        # genuinely supported.
        for row in self._rows_newest_first():
            if (
                row["logical_key"] == logical_key
                and row["status"] == ComputationStatus.SUCCEEDED
                and row.get("cache_status") != CacheStatus.HIT
            ):
                return self._stored(row)
        return None

    def lock_for(self, fingerprint: str) -> asyncio.Lock:
        """Stand-in for the Redis stampede lock (§37) in single-process mode."""
        lock = self._locks.get(fingerprint)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[fingerprint] = lock
        return lock

    def _insert(self, **fields: Any) -> dict[str, Any]:
        row = {"_seq": len(self.computations), **fields}
        self.computations[fields["id"]] = row
        return row

    # -- §29 lookup -------------------------------------------------------

    async def lookup(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = LookupRequest(
            name=payload["name"],
            logical_key=payload["logical_key"],
            fingerprint=payload["fingerprint"],
            run_id=payload.get("run_id"),
            ttl_seconds=payload.get("ttl_seconds"),
            force=bool(payload.get("force", False)),
            cross_model_reuse=bool(payload.get("cross_model_reuse", False)),
            artifact_type=payload.get("artifact_type"),
            model_agnostic_fingerprint=payload.get("model_agnostic_fingerprint", ""),
            model=payload.get("model"),
        )
        now = self.now()

        exact = self._find_exact(request.fingerprint)
        previous = self._find_previous(request.logical_key)
        outcome = classify(request, exact, previous, now)
        outcome = upgrade_for_cross_model(
            outcome,
            request,
            previous,
            is_portable=(previous.artifact_type in DEFAULT_PORTABLE_ARTIFACT_TYPES)
            if previous is not None
            else False,
            now=now,
            max_age_seconds=request.ttl_seconds,
        )

        if outcome.status != CacheStatus.HIT:
            return {
                "status": outcome.status,
                "previous_computation_id": outcome.previous_computation_id,
                "reason": outcome.reason,
            }

        source = outcome.computation
        assert source is not None
        # A same-model HIT resolves an exact fingerprint match; anything else
        # that reached HIT only got here via upgrade_for_cross_model.
        reuse_kind = None if source.fingerprint == request.fingerprint else "CROSS_MODEL"

        # Record the reuse as a node of this run so /runs/{id} and the graph
        # can report it. The observation row is not itself a reuse source.
        observation_id = _new_id()
        self._insert(
            id=observation_id,
            run_id=request.run_id,
            name=request.name,
            logical_key=request.logical_key,
            fingerprint=request.fingerprint,
            status=ComputationStatus.SUCCEEDED,
            cache_status=CacheStatus.HIT,
            reuse_kind=reuse_kind,
            model=request.model or source.model,
            input_json=None,
            output_json=None,
            output_hash=source.output_hash,
            cost_usd=0.0,
            saved_usd=source.cost_usd,
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            reusable=False,
            reused_from=source.id,
            expires_at=None,
            metadata={},
            created_at=now,
            completed_at=now,
        )
        self.dependencies[observation_id] = list(payload.get("dependencies") or [])
        self._event(observation_id, "LOOKUP_STARTED", fingerprint=request.fingerprint)
        self._event(
            observation_id,
            "CACHE_HIT",
            source_computation_id=source.id,
            reuse_kind=reuse_kind,
        )

        return {
            "status": CacheStatus.HIT,
            "reuse_kind": reuse_kind,
            "computation": {
                "id": observation_id,
                "source_computation_id": source.id,
                "output": source.output_json,
                "output_hash": source.output_hash,
                "cost_usd": source.cost_usd,
                "input_tokens": source.input_tokens,
                "output_tokens": source.output_tokens,
                "created_at": _iso(source.created_at),
            },
            "reason": outcome.reason,
        }

    # -- §30 start --------------------------------------------------------

    async def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = self.now()
        computation_id = _new_id()
        ttl_seconds = payload.get("ttl_seconds")
        expires_at = (
            now + _dt.timedelta(seconds=int(ttl_seconds)) if ttl_seconds else None
        )
        execution = payload.get("execution") or {}

        self._insert(
            id=computation_id,
            run_id=payload.get("run_id"),
            name=payload["name"],
            logical_key=payload["logical_key"],
            fingerprint=payload["fingerprint"],
            status=ComputationStatus.RUNNING,
            cache_status=payload.get("cache_status", CacheStatus.MISS),
            input_json=payload.get("input_json"),
            output_json=None,
            output_hash=None,
            model=execution.get("model"),
            provider=execution.get("provider"),
            prompt_hash=execution.get("prompt_hash"),
            tool_schema_hash=execution.get("tool_schema_hash"),
            code_version=execution.get("code_version"),
            artifact_type=payload.get("artifact_type"),
            model_agnostic_fingerprint=payload.get("model_agnostic_fingerprint"),
            reuse_kind=None,
            cost_usd=0.0,
            saved_usd=0.0,
            input_tokens=0,
            output_tokens=0,
            latency_ms=None,
            ttl_seconds=ttl_seconds,
            reusable=bool(payload.get("reusable", True)),
            expires_at=expires_at,
            metadata=payload.get("metadata") or {},
            created_at=now,
            started_at=now,
            completed_at=None,
        )
        self.dependencies[computation_id] = list(payload.get("dependencies") or [])
        self._event(computation_id, "EXECUTION_STARTED", name=payload["name"])
        return {"computation_id": computation_id}

    # -- §31 complete -----------------------------------------------------

    async def complete(
        self, computation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        row = self.computations[computation_id]
        now = self.now()
        row.update(
            status=ComputationStatus.SUCCEEDED,
            output_json=payload.get("output_json"),
            output_hash=payload.get("output_hash"),
            input_tokens=int(payload.get("input_tokens", 0)),
            output_tokens=int(payload.get("output_tokens", 0)),
            cost_usd=float(payload.get("cost_usd", 0.0)),
            latency_ms=payload.get("latency_ms"),
            completed_at=now,
        )
        if payload.get("model"):
            row["model"] = payload["model"]
        if payload.get("provider"):
            row["provider"] = payload["provider"]
        self._event(computation_id, "OUTPUT_HASHED", output_hash=row["output_hash"])
        self._event(computation_id, "RESULT_STORED")
        return {"status": ComputationStatus.SUCCEEDED}

    # -- §32 fail ---------------------------------------------------------

    async def fail(self, computation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = self.computations[computation_id]
        row.update(
            status=ComputationStatus.FAILED,
            reusable=False,  # failed computations must never be reused (§3)
            completed_at=self.now(),
            metadata={
                **row.get("metadata", {}),
                "error_type": payload.get("error_type"),
                "error_message": payload.get("error_message"),
            },
        )
        self._event(
            computation_id,
            "EXECUTION_FAILED",
            error_type=payload.get("error_type"),
            error_message=payload.get("error_message"),
        )
        return {"status": ComputationStatus.FAILED}

    # -- §33 resources ----------------------------------------------------

    async def upsert_resource(self, payload: dict[str, Any]) -> dict[str, Any]:
        key = payload["resource_key"]
        version = payload["version"]
        existing = self.resources.get(key)
        previous_version = existing["current_version"] if existing else None
        self.resources[key] = {
            "resource_key": key,
            "current_version": version,
            "metadata": payload.get("metadata") or {},
            "updated_at": self.now(),
        }
        return {
            "changed": previous_version != version,
            "previous_version": previous_version,
            "current_version": version,
        }

    # -- runs -------------------------------------------------------------

    async def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = _new_id()
        self.runs[run_id] = {
            "id": run_id,
            "external_run_id": payload.get("external_run_id"),
            "status": "RUNNING",
            "metadata": payload.get("metadata") or {},
            "started_at": self.now(),
            "finished_at": None,
        }
        return {"id": run_id}

    async def finish_run(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        run = self.runs[run_id]
        run["status"] = payload.get("status", "SUCCEEDED")
        run["finished_at"] = self.now()
        return await self.get_run(run_id)

    def _run_rows(self, run_id: str) -> list[dict[str, Any]]:
        return [
            row
            for row in self.computations.values()
            if row.get("run_id") == run_id
        ]

    async def get_run(self, run_id: str) -> dict[str, Any]:
        run = self.runs.get(run_id, {"id": run_id, "status": "RUNNING"})
        rows = self._run_rows(run_id)
        counts = {CacheStatus.HIT: 0, CacheStatus.MISS: 0, CacheStatus.STALE: 0,
                  CacheStatus.FORCED: 0}
        for row in rows:
            counts[row.get("cache_status", CacheStatus.MISS)] = (
                counts.get(row.get("cache_status", CacheStatus.MISS), 0) + 1
            )
        return {
            "id": run_id,
            "status": run.get("status", "RUNNING"),
            "computations": len(rows),
            "hits": counts[CacheStatus.HIT],
            "misses": counts[CacheStatus.MISS],
            "stale": counts[CacheStatus.STALE],
            "forced": counts[CacheStatus.FORCED],
            "total_cost_usd": round(sum(r.get("cost_usd", 0.0) for r in rows), 8),
            "saved_usd": round(sum(r.get("saved_usd", 0.0) for r in rows), 8),
            "input_tokens": sum(r.get("input_tokens", 0) for r in rows),
            "output_tokens": sum(r.get("output_tokens", 0) for r in rows),
        }

    async def get_run_graph(self, run_id: str) -> dict[str, Any]:
        rows = self._run_rows(run_id)
        by_id = {row["id"]: row for row in rows}
        nodes = [
            {
                "id": row["id"],
                "name": row["name"],
                "status": row.get("cache_status", CacheStatus.MISS),
                "cost_usd": row.get("cost_usd", 0.0),
                "saved_usd": row.get("saved_usd", 0.0),
                "latency_ms": row.get("latency_ms"),
                "input_tokens": row.get("input_tokens", 0),
                "output_tokens": row.get("output_tokens", 0),
                "reuse_kind": row.get("reuse_kind"),
            }
            for row in rows
        ]
        edges = []
        for row in rows:
            for dependency in self.dependencies.get(row["id"], []):
                source = dependency.get("source_computation_id")
                if source and source in by_id:
                    edges.append({"from": source, "to": row["id"],
                                  "key": dependency["key"]})
        return {"nodes": nodes, "edges": edges}

    async def get_metrics(self, period: str = "30d") -> dict[str, Any]:
        rows = list(self.computations.values())
        hits = [r for r in rows if r.get("cache_status") == CacheStatus.HIT]
        total = len(rows)

        # Counted once per reuse, not once per distinct source: a source reused
        # twenty times avoided its tokens twenty times.
        tokens_avoided = 0
        llm_calls_avoided = 0
        for row in hits:
            source = self.computations.get(row.get("reused_from"))
            if source is None:
                continue
            tokens_avoided += source.get("input_tokens", 0) + source.get(
                "output_tokens", 0
            )
            if source.get("model"):
                llm_calls_avoided += 1

        return {
            "period": period,
            "runs": len(self.runs),
            "computations": total,
            "hit_rate": (len(hits) / total) if total else 0.0,
            "cost_usd": round(sum(r.get("cost_usd", 0.0) for r in rows), 8),
            "saved_usd": round(sum(r.get("saved_usd", 0.0) for r in rows), 8),
            "tokens_consumed": sum(
                r.get("input_tokens", 0) + r.get("output_tokens", 0) for r in rows
            ),
            "tokens_avoided": tokens_avoided,
            "llm_calls_avoided": llm_calls_avoided,
        }

    # -- §53 explain ------------------------------------------------------

    async def explain(self, computation_id: str) -> dict[str, Any]:
        row = self.computations[computation_id]
        previous = None
        for candidate in self._rows_newest_first():
            if (
                candidate["logical_key"] == row["logical_key"]
                and candidate["id"] != computation_id
                and candidate["created_at"] <= row["created_at"]
            ):
                previous = candidate
                break

        changes: list[dict[str, Any]] = []
        if previous is not None:
            old = {d["key"]: d for d in self.dependencies.get(previous["id"], [])}
            new = {d["key"]: d for d in self.dependencies.get(computation_id, [])}
            for key, dependency in new.items():
                before = old.get(key)
                if before is None:
                    changes.append({"kind": "dependency_added", "key": key,
                                    "new": dependency["version"]})
                elif before["version"] != dependency["version"]:
                    changes.append({"kind": "dependency_changed", "key": key,
                                    "old": before["version"],
                                    "new": dependency["version"]})
            for key in old.keys() - new.keys():
                changes.append({"kind": "dependency_removed", "key": key})
            for field in ("model", "prompt_hash", "tool_schema_hash", "code_version"):
                if previous.get(field) != row.get(field):
                    changes.append({"kind": f"{field}_changed",
                                    "old": previous.get(field),
                                    "new": row.get(field)})

        return {
            "computation_id": computation_id,
            "name": row["name"],
            "cache_status": row.get("cache_status"),
            "previous_computation_id": previous["id"] if previous else None,
            "changes": changes,
        }

    async def aclose(self) -> None:
        return None
