"""Projects (spec §6.2)."""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import CheckConstraint, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, uuid_fk, uuid_pk

PROJECT_KINDS = ("chat", "build")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug"),
        CheckConstraint("kind IN ('chat','build')", name="ck_projects_kind"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = uuid_fk("workspaces.id")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    #: Which sidebar tab this conversation belongs to (V0.3 Chat/Build
    #: toggle) -- set once at creation from the entry point the user
    #: started from (ChatThread.tsx's initialMode), never changed after.
    #: Existing rows default to "chat" (nothing "build" existed before this).
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="chat", server_default="chat")
    created_at: Mapped[_dt.datetime] = created_at_column()
