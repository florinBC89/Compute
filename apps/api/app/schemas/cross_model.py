"""Model-switch preview (V0.2, spec section 4 of the product doc).

Shows what would carry over *before* executing anything with a different
model -- the pre-execution, project-wide analog of what
``GET /computations/{id}/explain`` already does retroactively for one row.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.computation import ArtifactType


class PreviewModelSwitchRequest(BaseModel):
    target_model: str


class PreviewItem(BaseModel):
    name: str
    logical_key: str
    decision: Literal["REUSE", "RECOMPUTE"]
    reason: str
    artifact_type: ArtifactType | None = None
    current_model: str | None = None
    #: What re-running this logical key would cost if it does NOT reuse --
    #: the source row's own recorded cost, used to size the preview's
    #: "estimated incremental cost" figure (spec section 4).
    cost_if_recomputed_usd: float = 0.0


class PreviewModelSwitchResponse(BaseModel):
    target_model: str
    items: list[PreviewItem]
    reusable_count: int
    recompute_count: int
    estimated_incremental_cost_usd: float
