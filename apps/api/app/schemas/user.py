"""Current-user identity (V0.2 human-workspace slice)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProjectSummary(BaseModel):
    id: str
    name: str
    slug: str
    #: Chat/Build sidebar tab this conversation belongs to (V0.3) -- see
    #: app.models.project.Project.kind.
    kind: Literal["chat", "build"] = "chat"


class MeResponse(BaseModel):
    user_id: str
    email: str
    workspace_id: str
    workspace_name: str
    projects: list[ProjectSummary]
