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

    本表为真源，工作目录下的 ``memory/MEMORY.md`` 由 ``LongTermMemory.sync_markdown()``
    全量渲染，是只读镜像。
    """

    __tablename__ = "space_memory"

    # 主键，由 next_id() 生成，不走数据库自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    # 所属空间，space.id；空间删除时级联删除
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 记忆分类：fact-事实，decision-决策，preference-偏好，issue-已知问题，glossary-术语
    category: Mapped[str] = mapped_column(Text, nullable=False, default="fact")
    # 标签，JSON 数组字符串
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # 来源会话，conversation.id；会话删除时置空
    source_conversation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("conversation.id", ondelete="SET NULL"), default=None
    )
    # 1-生效，0-失效；失效条目不参与召回
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
