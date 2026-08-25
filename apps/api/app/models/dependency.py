"""Computation dependencies (spec §6.5)."""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import CheckConstraint, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, uuid_fk, uuid_pk

DEPENDENCY_TYPES = (
    "EXTERNAL",
    "COMPUTATION",
    "FILE",
    "API",
    "DATABASE",
    "MANUAL",
)


class ComputationDependency(Base):
    __tablename__ = "computation_dependencies"
    __table_args__ = (
        UniqueConstraint("computation_id", "dependency_key"),
        CheckConstraint(
            "dependency_type IN "
            "('EXTERNAL','COMPUTATION','FILE','API','DATABASE','MANUAL')",
            name="ck_dependency_type",
        ),
        Index("idx_dependencies_key", "dependency_key", "dependency_version"),
        Index("idx_dependencies_source", "source_computation_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    computation_id: Mapped[uuid.UUID] = uuid_fk("computations.id", ondelete="CASCADE")
    dependency_key: Mapped[str] = mapped_column(Text, nullable=False)
    dependency_version: Mapped[str] = mapped_column(Text, nullable=False)
    dependency_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="EXTERNAL", server_default="'EXTERNAL'"
    )
    source_computation_id: Mapped[uuid.UUID | None] = uuid_fk(
        "computations.id", nullable=True
    )
    created_at: Mapped[_dt.datetime] = created_at_column()
