from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.test_case import TestCase
    from src.data.models.test_run import TestRun


class TestResult(Base):
    """测试结果表"""

    __tablename__ = "test_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_run.id", ondelete="CASCADE"), nullable=False)
    test_case_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_case.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[str] = mapped_column(Text, nullable=False)
    case_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    request_url: Mapped[str] = mapped_column(Text, default="")
    request_method: Mapped[str] = mapped_column(Text, default="")
    request_headers: Mapped[str] = mapped_column(Text, default="{}")
    request_body: Mapped[str | None] = mapped_column(Text, default=None)
    query_params: Mapped[str | None] = mapped_column(Text, default=None)
    response_status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    response_headers: Mapped[str] = mapped_column(Text, default="{}")
    response_body: Mapped[str | None] = mapped_column(Text, default=None)
    response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[str | None] = mapped_column(Text, default=None)
    finished_at: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    test_run: Mapped[TestRun] = relationship(back_populates="test_results")
    test_case: Mapped[TestCase] = relationship(back_populates="test_results")

    __table_args__ = (
        CheckConstraint("status IN ('pending','running','passed','failed','skipped','error')", name="ck_result_status"),
        Index("idx_result_run", "run_id"),
        Index("idx_result_case", "test_case_id"),
    )
