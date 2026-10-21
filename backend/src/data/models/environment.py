from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.space import Space
    from src.data.models.test_run import TestRun


class Environment(Base):
    """测试环境表"""

    __tablename__ = "environment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    variables: Mapped[str] = mapped_column(Text, default="{}")
    is_default: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 生产环境标记：send_request 工具会据此拦截请求，避免污染真实数据
    is_production: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    space: Mapped[Space] = relationship(back_populates="environments")
    test_runs: Mapped[list[TestRun]] = relationship(back_populates="environment")

    __table_args__ = (Index("idx_env_space", "space_id"),)
