from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.agent_run import AgentRun
    from src.data.models.conversation import Conversation
    from src.data.models.endpoint import Endpoint
    from src.data.models.environment import Environment
    from src.data.models.knowledge import KnowledgeDocument
    from src.data.models.space_memory import SpaceMemory


class Space(Base):
    """空间表 - 管理多个被测服务

    一个空间对应一个工作目录（``workspace_path``），目录同时是 Agent 的沙箱、
    测试资产的落地处、以及空间级约定（``AGENTS.md``）的载体。
    """

    __tablename__ = "space"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    workspace_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    endpoints: Mapped[list[Endpoint]] = relationship(back_populates="space", cascade="all, delete-orphan")
    environments: Mapped[list[Environment]] = relationship(back_populates="space", cascade="all, delete-orphan")
    agent_runs: Mapped[list[AgentRun]] = relationship(back_populates="space", cascade="all, delete-orphan")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="space", cascade="all, delete-orphan")
    memories: Mapped[list[SpaceMemory]] = relationship(back_populates="space", cascade="all, delete-orphan")
    documents: Mapped[list[KnowledgeDocument]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_space_name", "name"),)
