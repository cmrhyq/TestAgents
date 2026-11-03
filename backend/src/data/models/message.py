from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.conversation import Conversation


class Message(Base):
    """消息表 - 会话中的单条消息，只追加不修改。"""

    __tablename__ = "message"

    # 主键，由 next_id() 生成，不走数据库自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    # 所属会话，conversation.id；会话删除时级联删除
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    # 角色，取值 user / assistant / system
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 附加信息，JSON 对象字符串，可含 token 用量、附件路径、关联的 run_id
    meta: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant','system')", name="ck_message_role"),
        Index("idx_message_conv", "conversation_id"),
    )
