from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.conversation import Conversation


class Message(Base):
    """消息表 - 会话中的单条消息（append-only）"""

    __tablename__ = "message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    meta: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant','system')", name="ck_message_role"),
        Index("idx_message_conv", "conversation_id"),
    )
