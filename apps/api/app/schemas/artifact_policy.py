"""Cross-model reuse portability policy (V0.2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.computation import ArtifactType

PolicyScope = Literal["workspace", "project"]
PolicySource = Literal["project", "workspace", "default"]


class ArtifactPolicyEntry(BaseModel):
    artifact_type: ArtifactType
    portable: bool
    #: Which level this value came from -- a project override, a
    #: workspace-level default row, or the hardcoded fallback (see
    #: computelayer.semantics.DEFAULT_PORTABLE_ARTIFACT_TYPES) when neither
    #: exists yet.
    source: PolicySource


class ArtifactPolicyListResponse(BaseModel):
    policies: list[ArtifactPolicyEntry]


class ArtifactPolicyUpdateRequest(BaseModel):
    portable: bool
    #: "workspace" sets the default for every project in this workspace;
    #: "project" overrides it for the project the request is scoped to.
    scope: PolicyScope = "workspace"
