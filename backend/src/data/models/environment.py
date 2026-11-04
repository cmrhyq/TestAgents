from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.agent_run import AgentRun
    from src.data.models.space import Space


class Environment(Base):
    """测试环境表 - 空间下的可执行目标，由基础地址与变量组成。

    环境变量以 JSON 字符串存于 ``variables``，解析后作为 ``base_url`` 之外的占位符来源。
    """

    __tablename__ = "environment"

    # 主键，由 next_id() 生成，不走数据库自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    # 所属空间，space.id；空间删除时级联删除
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # 环境基础地址，不含末尾斜杠；请求 URL 由此拼接 path
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    # 环境变量，JSON 对象字符串，默认空对象
    variables: Mapped[str] = mapped_column(Text, default="{}")
    # 1-默认环境，0-非默认；空间内默认环境用于未指定环境的请求
    is_default: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 生产环境标记：1-生产，0-非生产；send_request 据此拦截写请求
    is_production: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 1-启用，2-禁用；取值与 DataStatus 一致
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    space: Mapped[Space] = relationship(back_populates="environments")
    agent_runs: Mapped[list[AgentRun]] = relationship(back_populates="environment")

    __table_args__ = (Index("idx_env_space", "space_id"),)
