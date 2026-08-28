"""Job events -- progress stream for one consumer-workspace research task
(V0.2 human-workspace slice). Append-only, tailed by the jobs SSE endpoint.
Same shape as `computation_events`, scoped to a job instead of a
computation.
"""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import BigInteger, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, uuid_fk

JOB_EVENT_TYPES = (
    "QUEUED",
    "STARTED",
    "STEP_STARTED",
    "STEP_FINISHED",
    "COST_CAP_REACHED",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
)


class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (Index("idx_job_events_job", "job_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = uuid_fk("jobs.id", ondelete="CASCADE")
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[_dt.datetime] = created_at_column()
