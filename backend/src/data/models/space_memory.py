from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.conversation import Conversation
    from src.data.models.space import Space


class SpaceMemory(Base):
    """跨会话记忆 - 按空间隔离的长期记忆条目。

    真源是这张表；``workspaces/{space_id}/memory/MEMORY.md`` 只是它的只读镜像，
    由 ``LongTermMemory.sync_markdown()`` 全量渲染，方便 Agent 用读文件的方式取记忆。
    """

    __tablename__ = "space_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # fact=事实 decision=决策 preference=偏好 issue=已知问题 glossary=术语
    category: Mapped[str] = mapped_column(Text, nullable=False, default="fact")
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source_conversation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("conversation.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    space: Mapped[Space] = relationship(back_populates="memories")
    source_conversation: Mapped[Conversation | None] = relationship()

    __table_args__ = (
        CheckConstraint(
            "category IN ('fact','decision','preference','issue','glossary')",
            name="ck_memory_category",
        ),
        CheckConstraint("status IN (0,1)", name="ck_memory_status"),
        Index("idx_memory_space", "space_id", "status"),
        Index("idx_memory_category", "space_id", "category"),
    )
