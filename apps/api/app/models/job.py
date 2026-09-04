"""Jobs -- orchestration state for one consumer-workspace research task
(V0.2 human-workspace slice).

Deliberately separate from `runs`: `runs` is the SDK's spec-defined
compute-grouping, driven purely by `compute.run()` calls, and its schema is
owned by the cross-model-reuse contract. `jobs` is orchestration-level state
(queued/running/cancellation/spend-cap) that has no reason to live there. A
job creates and owns exactly one `runs` row once the worker picks it up.
"""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, uuid_fk, uuid_pk

JOB_STATUSES = ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_jobs_status",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = uuid_fk("workspaces.id")
    project_id: Mapped[uuid.UUID] = uuid_fk("projects.id")
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    run_id: Mapped[uuid.UUID | None] = uuid_fk("runs.id", nullable=True)

    task_text: Mapped[str] = mapped_column(Text, nullable=False)
    #: The clean assistant-facing reply (V0.3 chat) -- distinct from the
    #: internal step artifacts it's drawn from (today, write_draft's
    #: output). Populated once the job SUCCEEDS; None until then and for
    #: any job that doesn't finish successfully.
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_preference: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: "Lazy" mode (V0.3 chat): appends a code-minimalism ruleset to this
    #: turn's system prompt -- see app.agent.chat.LAZY_MODE_SYSTEM_SUFFIX.
    #: Set once at job creation, same lifecycle as model_preference (a
    #: Regenerate reuses the same job row, so it reuses this too).
    lazy_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="QUEUED", server_default="QUEUED"
    )
    current_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    cost_cap_usd: Mapped[float] = mapped_column(
        Numeric(18, 8), nullable=False, default=0.50, server_default="0.50"
    )
    spent_usd: Mapped[float] = mapped_column(
        Numeric(18, 8), nullable=False, default=0, server_default="0"
    )

    created_at: Mapped[_dt.datetime] = created_at_column()
    started_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
