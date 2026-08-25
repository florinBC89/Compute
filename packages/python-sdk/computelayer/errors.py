"""Exception hierarchy for the ComputeLayer SDK."""

from __future__ import annotations

__all__ = [
    "ComputeLayerError",
    "ConfigurationError",
    "TransportError",
    "APIError",
    "DuplicateDependencyError",
    "ComputationFailed",
]


class ComputeLayerError(Exception):
    """Base class for every error raised by the SDK."""


class ConfigurationError(ComputeLayerError):
    """The client was constructed with missing or contradictory settings."""


class TransportError(ComputeLayerError):
    """The ComputeLayer API could not be reached."""


class APIError(ComputeLayerError):
    """The ComputeLayer API returned an error response."""

    def __init__(self, status_code: int, message: str, payload: object = None) -> None:
        super().__init__(f"ComputeLayer API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.payload = payload


class DuplicateDependencyError(ComputeLayerError):
    """The same dependency key was declared twice with different versions.

    ``computation_dependencies`` is unique on ``(computation_id, dependency_key)``
    (§6.5), and silently picking a winner would risk incorrect reuse.
    """


class ComputationFailed(ComputeLayerError):
    """A computation function raised; the failure was recorded (§32)."""
