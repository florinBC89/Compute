"""ComputeLayer -- deterministic incremental compute for AI agents.

    from computelayer import ComputeLayer

    cl = ComputeLayer(api_key="cl_test_...", project="research-agent")

    result = await cl.compute.run(
        name="analyze_financials",
        inputs={"company": "NVDA", "period": "FY2025"},
        dependencies=[cl.dep("financials:NVDA", version="sha256:abc123")],
        fn=analyze_financials,
    )

V0.1 solves exactly one problem: *do not rerun unchanged AI work.*
"""

from __future__ import annotations

from computelayer.client import ComputeLayer
from computelayer.context import ExecutionMetrics, LLMCall, record_llm_call
from computelayer.dependency import Dependency, DependencyType, dep
from computelayer.errors import (
    APIError,
    ComputationFailed,
    ComputeLayerError,
    ConfigurationError,
    DuplicateDependencyError,
    TransportError,
)
from computelayer.hashing import (
    build_fingerprint,
    build_logical_key,
    build_model_agnostic_fingerprint,
    get_code_version,
    hash_json,
    hash_text,
    sha256_hex,
    sha256_json,
)
from computelayer.result import CacheStatus, ComputationStatus, ComputeResult
from computelayer.secrets import Secret, secret
from computelayer.semantics import StoredComputation, classify, is_reusable
from computelayer.serialization import (
    SPEC_VERSION,
    CanonicalizationError,
    RefMode,
    canonical_json,
    normalize,
)

__version__ = "0.1.0"
__spec_version__ = SPEC_VERSION

__all__ = [
    "ComputeLayer",
    "ComputeResult",
    "CacheStatus",
    "ComputationStatus",
    "Dependency",
    "DependencyType",
    "dep",
    "Secret",
    "secret",
    "RefMode",
    "SPEC_VERSION",
    "canonical_json",
    "normalize",
    "CanonicalizationError",
    "sha256_hex",
    "sha256_json",
    "hash_text",
    "hash_json",
    "build_fingerprint",
    "build_logical_key",
    "build_model_agnostic_fingerprint",
    "get_code_version",
    "StoredComputation",
    "classify",
    "is_reusable",
    "ExecutionMetrics",
    "LLMCall",
    "record_llm_call",
    "ComputeLayerError",
    "ConfigurationError",
    "TransportError",
    "APIError",
    "DuplicateDependencyError",
    "ComputationFailed",
    "__version__",
]
