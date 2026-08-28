"""End users of the consumer workspace app (V0.2 human-workspace slice).

Identity is owned by Supabase Auth -- this table only maps a Supabase user
id to the app-side data model (see app.services.user_scope), the same way
Workspace/Project already own everything a user's work touches. There is no
password or session data here; that lives in Supabase.
"""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, uuid_pk


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    supabase_user_id: Mapped[str] = mapped_column(
        Text, nullable=False, unique=True, index=True
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[_dt.datetime] = created_at_column()
