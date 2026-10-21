from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.test_run import TestRun


class TestSummary(Base):
    """测试摘要表"""

    __tablename__ = "test_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("test_run.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    min_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p95_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    failure_reasons: Mapped[str] = mapped_column(Text, default="{}")
    started_at: Mapped[str | None] = mapped_column(Text, default=None)
    finished_at: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    test_run: Mapped[TestRun] = relationship(back_populates="summary")

    __table_args__ = (
        Index("idx_summary_run", "run_id"),
        Index("idx_summary_pass_rate", "pass_rate"),
    )
