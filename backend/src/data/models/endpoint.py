from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.space import Space
    from src.data.models.test_case import TestCase


class Endpoint(Base):
    """API 定义表"""

    __tablename__ = "endpoint"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    operation_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    description: Mapped[str] = mapped_column(Text, default="")
    params: Mapped[str | None] = mapped_column(Text, default=None)
    headers: Mapped[str] = mapped_column(Text, default="{}")
    body: Mapped[str | None] = mapped_column(Text, default=None)
    responses: Mapped[str] = mapped_column(Text, default="[]")
    security: Mapped[str] = mapped_column(Text, default="[]")
    content_type: Mapped[str] = mapped_column(Text, default="application/json")
    deprecated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    space: Mapped[Space] = relationship(back_populates="endpoints")
    test_cases: Mapped[list[TestCase]] = relationship(back_populates="endpoint")

    __table_args__ = (
        CheckConstraint("method IN ('GET','POST','PUT','DELETE','PATCH','HEAD','OPTIONS')", name="ck_api_method"),
        UniqueConstraint("space_id", "path", "method", name="uq_space_path_method"),
        Index("idx_endpoint_space", "space_id"),
        Index("idx_endpoint_operation_id", "operation_id"),
    )
