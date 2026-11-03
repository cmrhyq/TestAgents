from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.agent_run import AgentRun


class Report(Base):
    """报告记录表 - 一次执行产出的报告文件元数据，文件正文不入库。"""

    __tablename__ = "report"

    # 主键，由 next_id() 生成，不走数据库自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    # 列名沿用 run_id，语义是所属执行记录；改名需同步 DB 列、ORM、schema 与前端类型
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agent_run.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属执行记录 ID（agent_run.id）",
    )
    # 报告格式，取值 excel / html / markdown / json
    format: Mapped[str] = mapped_column(Text, nullable=False)
    # 报告文件磁盘路径，下载时直接读取该文件
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    # 文件大小，字节；0 表示未统计
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    # 生成时间
    generated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    run: Mapped[AgentRun] = relationship(back_populates="reports")

    __table_args__ = (
        CheckConstraint("format IN ('excel','html','markdown','json')", name="ck_report_format"),
        Index("idx_report_run", "run_id"),
        Index("idx_report_format", "format"),
    )
