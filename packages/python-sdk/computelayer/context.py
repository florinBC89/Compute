"""Execution context: current run, current computation, LLM metrics (§25, §40).

Metrics are collected with :class:`contextvars.ContextVar` so concurrent
``compute.run`` calls in the same event loop never mix their token counts.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

__all__ = [
    "ExecutionMetrics",
    "LLMCall",
    "current_run_id",
    "set_current_run_id",
    "collect_metrics",
    "current_execution_metrics",
    "record_llm_call",
]


@dataclass
class LLMCall:
    model: str
    provider: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionMetrics:
    """Everything observed while one computation body executed."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    llm_calls: list[LLMCall] = field(default_factory=list)

    @property
    def llm_call_count(self) -> int:
        return len(self.llm_calls)

    @property
    def model(self) -> str | None:
        return self.llm_calls[-1].model if self.llm_calls else None

    @property
    def provider(self) -> str | None:
        for call in reversed(self.llm_calls):
            if call.provider:
                return call.provider
        return None

    def add(self, call: LLMCall) -> None:
        self.llm_calls.append(call)
        self.input_tokens += call.input_tokens
        self.output_tokens += call.output_tokens
        self.cost_usd += call.cost_usd


_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "computelayer_run_id", default=None
)
_metrics: contextvars.ContextVar[ExecutionMetrics | None] = contextvars.ContextVar(
    "computelayer_metrics", default=None
)


def current_run_id() -> str | None:
    return _run_id.get()


@contextmanager
def set_current_run_id(run_id: str | None) -> Iterator[None]:
    token = _run_id.set(run_id)
    try:
        yield
    finally:
        _run_id.reset(token)


@contextmanager
def collect_metrics() -> Iterator[ExecutionMetrics]:
    """Capture LLM usage emitted while the wrapped block runs."""
    metrics = ExecutionMetrics()
    token = _metrics.set(metrics)
    try:
        yield metrics
    finally:
        _metrics.reset(token)


def current_execution_metrics() -> ExecutionMetrics | None:
    """The metrics collector for the innermost active computation, if any."""
    return _metrics.get()


def record_llm_call(call: LLMCall) -> None:
    """Attribute one LLM call to the computation currently executing.

    Calls made outside any ``compute.run`` body are ignored rather than raising:
    instrumentation must never break the caller's program.
    """
    metrics = _metrics.get()
    if metrics is not None:
        metrics.add(call)
