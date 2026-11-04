from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.environment import Environment
    from src.data.models.message import Message
    from src.data.models.space import Space

# 工作模式：agent=自动选工具执行（默认）、ask=只回答、plan=只出计划
CONVERSATION_MODES = ("agent", "ask", "plan")


class Conversation(Base):
    """会话表 - 一次多轮对话的元数据。

    消息正文存放在 ``message`` 表，本表只保留归属、模式、选中的 skill 与环境绑定。
    ``status`` 为逻辑删除标记，删除会话时不做物理删除。
    """

    __tablename__ = "conversation"

    # 主键，由 next_id() 生成，不走数据库自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    # 所属空间，space.id；可空，空间删除时级联删除
    space_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), default=None)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 工作模式，取值 agent / ask / plan；与 skill_names 一起决定工具白名单
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="agent")
    # 本会话选中的 skill 名，JSON 数组字符串；空数组表示不额外限制
    skill_names: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # 绑定的测试环境，environment.id；send_request 据此解析 base_url 并做生产环境拦截
    environment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("environment.id", ondelete="SET NULL"), default=None
    )
    # 1-正常，0-已删除
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 最后一条消息时间，用于会话列表排序
    last_message_at: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    space: Mapped[Space | None] = relationship(back_populates="conversations")
    environment: Mapped[Environment | None] = relationship()
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at, Message.id",
    )

    __table_args__ = (
        CheckConstraint("mode IN ('agent','ask','plan')", name="ck_conversation_mode"),
        CheckConstraint("status IN (0,1)", name="ck_conversation_status"),
        Index("idx_conversation_space", "space_id"),
    )
