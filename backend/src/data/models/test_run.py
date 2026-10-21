from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.environment import Environment
    from src.data.models.space import Space
    from src.data.models.report import Report
    from src.data.models.test_case import TestCase
    from src.data.models.test_result import TestResult
    from src.data.models.test_summary import TestSummary


class TestRun(Base):
    """执行批次表"""

    __tablename__ = "test_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    environment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("environment.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    input_file: Mapped[str] = mapped_column(Text, default="")
    input_snapshot: Mapped[str] = mapped_column(Text, default="{}")
    config_snapshot: Mapped[str] = mapped_column(Text, default="{}")
    llm_provider: Mapped[str] = mapped_column(Text, default="")
    llm_model: Mapped[str] = mapped_column(Text, default="")
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    started_at: Mapped[str | None] = mapped_column(Text, default=None)
    finished_at: Mapped[str | None] = mapped_column(Text, default=None)
    total_duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    space: Mapped[Space] = relationship(back_populates="test_runs")
    environment: Mapped[Environment | None] = relationship(back_populates="test_runs")
    test_cases: Mapped[list[TestCase]] = relationship(back_populates="test_run", cascade="all, delete-orphan")
    test_results: Mapped[list[TestResult]] = relationship(back_populates="test_run", cascade="all, delete-orphan")
    summary: Mapped[TestSummary | None] = relationship(
        back_populates="test_run", uselist=False, cascade="all, delete-orphan"
    )
    reports: Mapped[list[Report]] = relationship(back_populates="test_run", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('pending','running','completed','failed','cancelled')", name="ck_run_status"),
        CheckConstraint("trigger_type IN ('manual','scheduled','ci')", name="ck_run_trigger"),
        Index("idx_run_space", "space_id"),
        Index("idx_run_env", "environment_id"),
    )
