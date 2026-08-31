"""Ethical -- a persistent named agent identity (Agent OS V0.4 slice).

Deliberately thin: this is "give Ethical a name and a face," not the full
Agent OS object model (spec §2-3) -- no Memory, no Skills/Tools, no
Policies beyond what a Job already enforces. An Ethical's "Work" is derived at
read time from its Project's existing Jobs (app.services.ethicals), not stored
here.
"""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, uuid_fk, uuid_pk


class Ethical(Base):
    __tablename__ = "ethicals"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = uuid_fk("workspaces.id")
    #: Not unique -- a Project can hold multiple Ethicals (spec §14's "Marketing
    #: Ethical / Research Ethical" under one Team Project). Work for now = that
    #: Project's Jobs, shared across any Ethical pointed at it, since Job has
    #: no ethical_id yet.
    project_id: Mapped[uuid.UUID] = uuid_fk("projects.id")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="active", server_default="active"
    )
    created_at: Mapped[_dt.datetime] = created_at_column()
