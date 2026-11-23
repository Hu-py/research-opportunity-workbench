"""Durable private and team conversations. Local messages are the source of truth."""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from research_workbench.core import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), default="新对话")
    owner_id: Mapped[str] = mapped_column(ForeignKey("team_members.id"), nullable=False, index=True)
    last_seq: Mapped[int] = mapped_column(Integer, default=0)
    last_ai_synced_seq: Mapped[int] = mapped_column(Integer, default=0)
    active_ai_call_id: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ChatMember(Base):
    __tablename__ = "chat_members"
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[str] = mapped_column(
        ForeignKey("team_members.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(16), default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    sender_id: Mapped[str | None] = mapped_column(ForeignKey("team_members.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(16), default="")
    client_nonce: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    __table_args__ = (
        UniqueConstraint("conversation_id", "seq", name="uq_chat_message_seq"),
        UniqueConstraint("conversation_id", "client_nonce", name="uq_chat_message_nonce"),
    )


class ChatAICall(Base):
    __tablename__ = "chat_ai_calls"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_messages.id"), nullable=True
    )
    assistant_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_messages.id"), nullable=True
    )
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    input_until_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)
    provider: Mapped[str] = mapped_column(String(24), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    provider_response_id: Mapped[str] = mapped_column(String(160), default="")
    usage_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint("conversation_id", "idempotency_key", name="uq_chat_ai_idempotency"),
    )
