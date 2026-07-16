"""Conversation model for dialog persistence."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


def _default_expired_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=24)


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), unique=True, default=lambda: str(uuid.uuid4())
    )
    messages: Mapped[list] = mapped_column(JSON, default=list)
    expired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_default_expired_at
    )
    summary: Mapped[str | None] = mapped_column(Text, default=None)
