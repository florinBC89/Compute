"""Runs -- one complete agent invocation (spec §6.3)."""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_fk, uuid_pk

RUN_STATUSES = ("RUNNING", "SUCCEEDED", "FAILED")


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED')", name="ck_runs_status"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = uuid_fk("workspaces.id")
    project_id: Mapped[uuid.UUID] = uuid_fk("projects.id")
    external_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="RUNNING")
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
    total_input_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    total_output_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    estimated_cost_usd: Mapped[float] = mapped_column(
        Numeric(18, 8), nullable=False, default=0, server_default="0"
    )
    estimated_saved_usd: Mapped[float] = mapped_column(
        Numeric(18, 8), nullable=False, default=0, server_default="0"
    )
    started_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
