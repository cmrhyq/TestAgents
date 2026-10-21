from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.endpoint import Endpoint
    from src.data.models.test_result import TestResult
    from src.data.models.test_run import TestRun


class TestCase(Base):
    """测试用例表"""

    __tablename__ = "test_case"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_run.id", ondelete="CASCADE"), nullable=False)
    endpoint_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("endpoint.id", ondelete="SET NULL"))
    case_id: Mapped[str] = mapped_column(Text, nullable=False)
    case_name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_type: Mapped[str] = mapped_column(Text, nullable=False, default="normal")
    priority: Mapped[str] = mapped_column(Text, nullable=False, default="P1")
    headers: Mapped[str] = mapped_column(Text, default="{}")
    body: Mapped[str | None] = mapped_column(Text, default=None)
    params: Mapped[str | None] = mapped_column(Text, default=None)
    cache_rules: Mapped[str | None] = mapped_column(Text, default=None)
    assert_rules: Mapped[str] = mapped_column(Text, default="[]")
    expected_result: Mapped[str] = mapped_column(Text, default="成功")
    description: Mapped[str] = mapped_column(Text, default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    unique_hash: Mapped[str] = mapped_column(Text, default="")
    generated_by: Mapped[str] = mapped_column(Text, nullable=False, default="llm")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    test_run: Mapped[TestRun] = relationship(back_populates="test_cases")
    endpoint: Mapped[Endpoint | None] = relationship(back_populates="test_cases")
    test_results: Mapped[list[TestResult]] = relationship(back_populates="test_case", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("method IN ('GET','POST','PUT','DELETE','PATCH','HEAD','OPTIONS')", name="ck_case_method"),
        CheckConstraint(
            "scenario_type IN ('normal','param_missing','param_type_error','boundary_value','permission_error','custom')",
            name="ck_case_scenario",
        ),
        CheckConstraint("priority IN ('P0','P1','P2')", name="ck_case_priority"),
        CheckConstraint("generated_by IN ('llm','manual','import')", name="ck_case_generated"),
        Index("idx_case_run", "run_id"),
        Index("idx_case_api", "endpoint_id"),
        Index("idx_case_case_id", "case_id"),
    )
