"""Report model for storing generated analysis reports."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Report(TimestampMixin, Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("conversations.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), default="Analysis Report")
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    sections: Mapped[dict] = mapped_column(JSON, default=dict)

    conversation = relationship("Conversation", backref="reports")
