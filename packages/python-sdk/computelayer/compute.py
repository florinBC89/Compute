"""``compute.run`` -- the primary SDK interface (spec §8, §10, §12, §40)."""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
from typing import Any, Callable, Iterable, Sequence

from computelayer.context import (
    ExecutionMetrics,
    collect_metrics,
    current_run_id,
)
from computelayer.dependency import Dependency, DependencyType
from computelayer.errors import ComputeLayerError
from computelayer.hashing import (
    build_fingerprint,
    build_logical_key,
    dedupe_dependencies,
    get_code_version,
    hash_json,
    hash_text,
    sha256_json,
)
from computelayer.locks import DEFAULT_LOCK_TTL_SECONDS
from computelayer.result import CacheStatus, ComputeResult
from computelayer.secrets import Secret
from computelayer.serialization import RefMode, normalize

__all__ = ["Compute", "extract_compute_dependencies"]

_POLL_INTERVAL_SECONDS = 0.05


# --------------------------------------------------------------------------
# §12 computation-as-dependency
# --------------------------------------------------------------------------


def extract_compute_dependencies(inputs: Any) -> list[Dependency]:
    """Find every :class:`ComputeResult` nested in ``inputs`` and make it a dep.

    The dependency *key* must be stable across runs, so it is built from the
    upstream logical key rather than its ``computation_id`` (which is a fresh
    UUID on every run and would make reuse impossible).  The dependency
    *version* is the upstream ``output_hash``, which is what makes §19
    propagation work: an upstream that re-executes to an identical output
    leaves this dependency -- and therefore this fingerprint -- unchanged.
    """
    from computelayer.result import ComputeResult

    found: list[Dependency] = []
    seen: set[int] = set()

    def walk(value: Any) -> None:
        if isinstance(value, ComputeResult):
            found.append(
                Dependency(
                    key=f"computation:{value.name}:{value.logical_key}",
                    version=value.output_hash,
                    type=DependencyType.COMPUTATION,
                    source_computation_id=value.computation_id,
                )
            )
            return
        if isinstance(value, Secret):
            return
        marker = id(value)
        if marker in seen:
            return
        if isinstance(value, dict):
            seen.add(marker)
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple, set, frozenset)):
            seen.add(marker)
            for item in value:
                walk(item)

    walk(inputs)
    return found


async def _maybe_await(fn: Callable[[], Any]) -> Any:
    result = fn()
    if inspect.isawaitable(result):
        return await result
    return result


class Compute:
    """Bound to a :class:`~computelayer.client.ComputeLayer` instance.

    Callable as a decorator (§10) and exposes :meth:`run` (§8).
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    # -- §8.1 -------------------------------------------------------------

    async def run(
        self,
        *,
        name: str,
        inputs: dict[str, Any],
        fn: Callable[[], Any],
        dependencies: Sequence[Dependency] | None = None,
        model: str | None = None,
        prompt: str | None = None,
        tools: Iterable[Any] | None = None,
        ttl: int | None = None,
        force: bool = False,
        reusable: bool = True,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> ComputeResult:
        client = self._client
        transport = client.transport

        inferred = extract_compute_dependencies(inputs)
        all_dependencies = dedupe_dependencies(list(dependencies or []) + inferred)

        prompt_hash = hash_text(prompt)
        tool_schema_hash = hash_json(list(tools) if tools is not None else None)
        code_version = get_code_version(client.code_version)

        logical_key = build_logical_key(name=name, inputs=inputs)
        fingerprint = build_fingerprint(
            name=name,
            inputs=inputs,
            dependencies=all_dependencies,
            model=model,
            prompt_hash=prompt_hash,
            tool_schema_hash=tool_schema_hash,
            code_version=code_version,
        )

        run_id = run_id or current_run_id()
        dependency_payload = [d.as_payload() for d in all_dependencies]

        lookup_payload = {
            "name": name,
            "logical_key": logical_key,
            "fingerprint": fingerprint,
            "run_id": run_id,
            "ttl_seconds": ttl,
            "force": force,
            "dependencies": dependency_payload,
        }

        cache_status = CacheStatus.FORCED if force else CacheStatus.MISS
        lookup: dict[str, Any] = {}

        if not force:
            lookup = await transport.lookup(lookup_payload)
            cache_status = lookup.get("status", CacheStatus.MISS)
            if cache_status == CacheStatus.HIT:
                return _result_from_hit(
                    lookup, name=name, fingerprint=fingerprint, logical_key=logical_key
                )

            # -- §37 stampede prevention ---------------------------------
            handle = await client.lock.acquire(
                f"{client.project}:{fingerprint}", DEFAULT_LOCK_TTL_SECONDS
            )
            if not handle.acquired:
                waited = await self._wait_for_winner(
                    transport, lookup_payload, client.lock_wait_seconds
                )
                if waited is not None:
                    return _result_from_hit(
                        waited,
                        name=name,
                        fingerprint=fingerprint,
                        logical_key=logical_key,
                    )
                handle = await client.lock.acquire(
                    f"{client.project}:{fingerprint}", DEFAULT_LOCK_TTL_SECONDS
                )
            else:
                # Double-check under the lock: a winner may have finished
                # between our lookup and our acquire.
                recheck = await transport.lookup(lookup_payload)
                if recheck.get("status") == CacheStatus.HIT:
                    await handle.release()
                    return _result_from_hit(
                        recheck,
                        name=name,
                        fingerprint=fingerprint,
                        logical_key=logical_key,
                    )
                cache_status = recheck.get("status", cache_status)
        else:
            handle = await client.lock.acquire(
                f"{client.project}:{fingerprint}", DEFAULT_LOCK_TTL_SECONDS
            )

        # -- execute ------------------------------------------------------
        start_payload = {
            "name": name,
            "logical_key": logical_key,
            "fingerprint": fingerprint,
            "run_id": run_id,
            "cache_status": cache_status,
            "input_json": (
                normalize(inputs, RefMode.PROVENANCE) if client.store_inputs else None
            ),
            "dependencies": dependency_payload,
            "ttl_seconds": ttl,
            "reusable": reusable,
            "metadata": metadata or {},
            "execution": {
                "model": model,
                "prompt_hash": prompt_hash,
                "tool_schema_hash": tool_schema_hash,
                "code_version": code_version,
            },
        }

        started = await transport.start(start_payload)
        computation_id = started["computation_id"]

        began = time.monotonic()
        try:
            with collect_metrics() as metrics:
                value = await _maybe_await(fn)
            latency_ms = int((time.monotonic() - began) * 1000)
        except BaseException as exc:
            await handle.release()
            await transport.fail(
                computation_id,
                {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:2000],
                },
            )
            raise

        try:
            normalized_output = normalize(value, RefMode.VERSION)
            output_hash = sha256_json(value)

            cost_usd = _resolve_cost(metrics, model)

            await transport.complete(
                computation_id,
                {
                    "output_json": normalized_output if client.store_outputs else None,
                    "output_hash": output_hash,
                    "input_tokens": metrics.input_tokens,
                    "output_tokens": metrics.output_tokens,
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                    "model": model or metrics.model,
                    "provider": metrics.provider,
                },
            )
        finally:
            await handle.release()

        return ComputeResult(
            value=value,
            computation_id=computation_id,
            cache_status=cache_status,
            fingerprint=fingerprint,
            output_hash=output_hash,
            logical_key=logical_key,
            name=name,
            input_tokens=metrics.input_tokens,
            output_tokens=metrics.output_tokens,
            cost_usd=cost_usd,
            saved_usd=0.0,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )

    async def _wait_for_winner(
        self, transport: Any, lookup_payload: dict[str, Any], wait_seconds: float
    ) -> dict[str, Any] | None:
        """Poll the lookup while another process computes this fingerprint."""
        deadline = time.monotonic() + wait_seconds
        poll_payload = {**lookup_payload, "run_id": lookup_payload.get("run_id")}
        while time.monotonic() < deadline:
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            result = await transport.lookup(poll_payload)
            if result.get("status") == CacheStatus.HIT:
                return result
        return None

    # -- §10 decorator ----------------------------------------------------

    def __call__(
        self,
        name: str | None = None,
        *,
        dependencies: Sequence[Dependency] | None = None,
        model: str | None = None,
        prompt: str | None = None,
        tools: Iterable[Any] | None = None,
        ttl: int | None = None,
        reusable: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Wrap a function so calling it normally goes through ``compute.run``."""

        def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
            signature = inspect.signature(func)
            computation_name = name or func.__name__

            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # ``force`` is consumed by ComputeLayer unless the wrapped
                # function declares it itself.
                force = False
                if "force" in kwargs and "force" not in signature.parameters:
                    force = bool(kwargs.pop("force"))

                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                # Positional and keyword arguments become canonical inputs.
                inputs = dict(bound.arguments)

                result = await self.run(
                    name=computation_name,
                    inputs=inputs,
                    fn=lambda: func(*args, **kwargs),
                    dependencies=dependencies,
                    model=model,
                    prompt=prompt,
                    tools=tools,
                    ttl=ttl,
                    force=force,
                    reusable=reusable,
                    metadata=metadata,
                )
                return result.value

            wrapper.compute_run = _make_result_variant(  # type: ignore[attr-defined]
                self, func, signature, computation_name, dependencies, model, prompt,
                tools, ttl, reusable, metadata
            )
            return wrapper

        return decorate


def _make_result_variant(
    compute: Compute,
    func: Callable[..., Any],
    signature: inspect.Signature,
    computation_name: str,
    dependencies: Sequence[Dependency] | None,
    model: str | None,
    prompt: str | None,
    tools: Iterable[Any] | None,
    ttl: int | None,
    reusable: bool,
    metadata: dict[str, Any] | None,
) -> Callable[..., Any]:
    """``fn.compute_run(...)`` returns the full ComputeResult, not just the value."""

    async def compute_run(*args: Any, force: bool = False, **kwargs: Any) -> ComputeResult:
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        return await compute.run(
            name=computation_name,
            inputs=dict(bound.arguments),
            fn=lambda: func(*args, **kwargs),
            dependencies=dependencies,
            model=model,
            prompt=prompt,
            tools=tools,
            ttl=ttl,
            force=force,
            reusable=reusable,
            metadata=metadata,
        )

    return compute_run


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _resolve_cost(metrics: ExecutionMetrics, model: str | None) -> float:
    """Cost observed during execution, or a local estimate if none was reported."""
    if metrics.cost_usd:
        return round(metrics.cost_usd, 8)
    if model and (metrics.input_tokens or metrics.output_tokens):
        from computelayer.pricing import estimate_cost

        return round(
            estimate_cost(model, metrics.input_tokens, metrics.output_tokens), 8
        )
    return 0.0


def _result_from_hit(
    lookup: dict[str, Any], *, name: str, fingerprint: str, logical_key: str
) -> ComputeResult:
    """Build a ComputeResult from a cache hit (§27: saved == reused cost)."""
    payload = lookup.get("computation") or {}
    if "output" not in payload:
        raise ComputeLayerError(
            "lookup returned HIT without an output; the stored computation "
            "may have been written with store_output=False"
        )
    return ComputeResult(
        value=payload.get("output"),
        computation_id=payload.get("id", ""),
        cache_status=CacheStatus.HIT,
        fingerprint=fingerprint,
        output_hash=payload.get("output_hash", ""),
        logical_key=logical_key,
        name=name,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        saved_usd=float(payload.get("cost_usd") or 0.0),
        latency_ms=0,
        metadata={"reused_from": payload.get("source_computation_id")},
    )
