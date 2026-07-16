"""Conversation persistence and retrieval service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.conversation import Conversation


MAX_HISTORY_ROUNDS = 50


class ConversationService:
    """Read/write conversation history with expiry and capacity enforcement."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Lookup ───────────────────────────────────────────

    def get_or_create(self, conversation_id: str | None) -> Conversation:
        """Return existing conversation or create a new one."""
        if conversation_id:
            conv = (
                self.db.query(Conversation)
                .filter(
                    Conversation.session_id == conversation_id,
                    Conversation.expired_at > datetime.now(timezone.utc),
                )
                .first()
            )
            if conv:
                return conv

        conv = Conversation()
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    # ── History ──────────────────────────────────────────

    def add_message(self, conv: Conversation, role: str, content: str) -> None:
        """Append a message and enforce round limit."""
        messages: list[dict[str, Any]] = list(conv.messages or [])
        messages.append({"role": role, "content": content, "timestamp": datetime.now(timezone.utc).isoformat()})

        # Enforce capacity — keep the *last* MAX_HISTORY_ROUNDS entries
        if len(messages) > MAX_HISTORY_ROUNDS * 2:  # user + assistant = 1 round
            messages = messages[-(MAX_HISTORY_ROUNDS * 2):]

        conv.messages = messages
        self.db.commit()

    def get_history(self, conv: Conversation) -> list[dict[str, Any]]:
        """Return the message history as a list of dicts."""
        return list(conv.messages or [])

    # ── Expiry ───────────────────────────────────────────

    def is_expired(self, conv: Conversation) -> bool:
        return conv.expired_at < datetime.now(timezone.utc)
