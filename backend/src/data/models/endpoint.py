from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.space import Space


class Endpoint(Base):
    """API 定义表 - 空间内的接口清单。

    同一空间下 ``path`` 与 ``method`` 组合唯一；结构类字段（``params`` / ``headers`` /
    ``body`` / ``responses`` / ``security``）均以 JSON 字符串存储，由 schema 层解析。
    """

    __tablename__ = "endpoint"

    # 主键，由 next_id() 生成，不走数据库自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    # 所属空间，space.id；空间删除时级联删除
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    # 接口来源标识（OpenAPI operationId 或生成的稳定标识）
    operation_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # 接口路径，含路径参数占位符
    path: Mapped[str] = mapped_column(Text, nullable=False)
    # HTTP 方法，取值受 __table_args__ 中的检查约束限定
    method: Mapped[str] = mapped_column(Text, nullable=False)
    # 标签，JSON 数组字符串
    tags: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    description: Mapped[str] = mapped_column(Text, default="")
    # 请求参数定义，JSON 对象字符串；NULL 表示未采集
    params: Mapped[str | None] = mapped_column(Text, default=None)
    # 请求头定义，JSON 对象字符串
    headers: Mapped[str] = mapped_column(Text, default="{}")
    # 请求体定义，JSON 对象字符串；NULL 表示无请求体
    body: Mapped[str | None] = mapped_column(Text, default=None)
    # 响应定义，JSON 数组字符串，按状态码分项
    responses: Mapped[str] = mapped_column(Text, default="[]")
    # 接口级认证方案，JSON 数组字符串
    security: Mapped[str] = mapped_column(Text, default="[]")
    content_type: Mapped[str] = mapped_column(Text, default="application/json")
    # 1-已废弃，0-正常
    deprecated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 1-启用，2-禁用，3-已删除，4-已废弃；取值与 DataStatus 一致
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 每次变更定义时递增，用于判断前端缓存是否失效
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    space: Mapped[Space] = relationship(back_populates="endpoints")

    __table_args__ = (
        CheckConstraint("method IN ('GET','POST','PUT','DELETE','PATCH','HEAD','OPTIONS')", name="ck_api_method"),
        UniqueConstraint("space_id", "path", "method", name="uq_space_path_method"),
        Index("idx_endpoint_space", "space_id"),
        Index("idx_endpoint_operation_id", "operation_id"),
    )
