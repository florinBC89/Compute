"""Maps a User to the workspace(s) they belong to (V0.2 human-workspace slice).

v1 only ever writes one 'owner' row per user, auto-created on first login
(see app.services.user_scope). Shaped so a later slice can add teams and
other roles without a schema change -- not built for that yet.
"""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import CheckConstraint, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, uuid_fk, uuid_pk

WORKSPACE_MEMBER_ROLES = ("owner",)


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        CheckConstraint("role IN ('owner')", name="ck_workspace_members_role"),
        Index(
            "ux_workspace_members_workspace_user",
            "workspace_id",
            "user_id",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = uuid_fk("workspaces.id")
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    role: Mapped[str] = mapped_column(
        Text, nullable=False, default="owner", server_default="owner"
    )
    created_at: Mapped[_dt.datetime] = created_at_column()
