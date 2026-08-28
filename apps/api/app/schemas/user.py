"""Current-user identity (V0.2 human-workspace slice)."""

from __future__ import annotations

from pydantic import BaseModel


class ProjectSummary(BaseModel):
    id: str
    name: str
    slug: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    workspace_id: str
    workspace_name: str
    projects: list[ProjectSummary]
