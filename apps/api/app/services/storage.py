"""Large-output policy (spec §38).

Outputs below the threshold live in JSONB.  Larger ones are written to object
storage and replaced by an artifact reference:

    {"__artifact__": true, "storage_uri": "...", "sha256": "..."}

V0.1 ships the policy and the reference shape; the object-storage driver is
pluggable and defaults to the local filesystem so the benchmark runs with no
cloud account.
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any

from app.config import get_settings

ARTIFACT_MARKER = "__artifact__"


def is_artifact_ref(value: Any) -> bool:
    return isinstance(value, dict) and value.get(ARTIFACT_MARKER) is True


def measure(value: Any) -> int:
    try:
        return len(json.dumps(value, separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


def store_output(value: Any, output_hash: str) -> Any:
    """Return the value to persist in ``computations.output_json``."""
    settings = get_settings()
    if value is None:
        return None
    if measure(value) < settings.large_output_threshold_bytes:
        return value

    uri = _write_artifact(value, output_hash, settings.object_storage_url)
    return {ARTIFACT_MARKER: True, "storage_uri": uri, "sha256": output_hash}


def load_output(value: Any) -> Any:
    """Resolve an artifact reference back into a value."""
    if not is_artifact_ref(value):
        return value
    uri = value.get("storage_uri", "")
    if uri.startswith("file://"):
        path = pathlib.Path(uri[len("file://") :])
        if path.exists():
            return json.loads(path.read_text("utf-8"))
    # Unresolvable reference: hand the reference back rather than inventing a
    # value. The SDK surfaces it and the caller can fetch it themselves.
    return value


def _write_artifact(value: Any, output_hash: str, base: str | None) -> str:
    base = base or "file:///var/lib/computelayer/artifacts"
    if not base.startswith("file://"):
        raise NotImplementedError(
            f"object storage backend for {base!r} is not implemented in V0.1; "
            "set OBJECT_STORAGE_URL to a file:// path"
        )
    directory = pathlib.Path(base[len("file://") :])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{output_hash}.json"
    if not path.exists():
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, separators=(",", ":")), "utf-8")
        os.replace(tmp, path)
    return f"file://{path}"
