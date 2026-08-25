"""Computation events -- trace debugging (spec §6.7)."""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import BigInteger, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, uuid_fk

EVENT_TYPES = (
    "LOOKUP_STARTED",
    "CACHE_HIT",
    "CACHE_MISS",
    "DEPENDENCY_CHANGED",
    "EXECUTION_STARTED",
    "LLM_CALL_STARTED",
    "LLM_CALL_FINISHED",
    "OUTPUT_HASHED",
    "RESULT_STORED",
    "EXECUTION_FAILED",
)


class ComputationEvent(Base):
    __tablename__ = "computation_events"
    __table_args__ = (Index("idx_events_computation", "computation_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    computation_id: Mapped[uuid.UUID] = uuid_fk("computations.id", ondelete="CASCADE")
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[_dt.datetime] = created_at_column()
