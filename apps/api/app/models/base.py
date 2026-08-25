"""Declarative base and shared column helpers."""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    pass


def uuid_pk():
    return mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


def uuid_fk(target: str, *, nullable: bool = False, ondelete: str | None = None):
    from sqlalchemy import ForeignKey

    return mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        index=True,
    )


def created_at_column():
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


def utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)
