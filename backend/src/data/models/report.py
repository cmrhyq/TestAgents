from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.agent_run import AgentRun


class Report(Base):
    """报告记录表"""

    __tablename__ = "report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    # 列名保持 run_id：语义就是「关联的执行 id」，改名要连锁改 DB 列、ORM、
    # schema、前端类型与下载文件名，收益为零。
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agent_run.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属执行记录 ID（agent_run.id）",
    )
    format: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    run: Mapped[AgentRun] = relationship(back_populates="reports")

    __table_args__ = (
        CheckConstraint("format IN ('excel','html','markdown','json')", name="ck_report_format"),
        Index("idx_report_run", "run_id"),
        Index("idx_report_format", "format"),
    )
