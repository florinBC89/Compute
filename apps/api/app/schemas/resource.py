"""Resource endpoints (spec §33)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResourceUpsertBody(BaseModel):
    resource_key: str
    version: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResourceUpsertResponse(BaseModel):
    changed: bool
    previous_version: str | None = None
    current_version: str
