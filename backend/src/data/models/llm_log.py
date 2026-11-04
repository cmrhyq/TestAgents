from __future__ import annotations

from sqlalchemy import Float, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.base import Base, local_now
from src.utils.id import next_id


class LLMLog(Base):
    """LLM 调用记录表：每次大模型请求的 token 用量、耗时与成本。

    由 ``LLMService`` 在调用结束后写入，数据取自 litellm 的用量元数据。
    ``space_id`` / ``conversation_id`` / ``run_id`` 均不建外键：所属对象被清理后，
    成本历史仍需保留。
    """

    __tablename__ = "llm_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    model_name: Mapped[str] = mapped_column(Text, nullable=False, comment="实际命中的模型（如 zai/glm-4-flash）")
    provider: Mapped[str] = mapped_column(Text, default="", comment="厂商（model_name 前缀）")
    request_type: Mapped[str] = mapped_column(Text, default="", comment="调用类型：invoke/ainvoke/stream/astream/tools")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, comment="输入 token 数")
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, comment="输出 token 数")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, comment="总 token 数")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, comment="调用耗时（毫秒）")
    success: Mapped[int] = mapped_column(Integer, default=1, comment="是否成功：1-成功 0-失败")
    error_message: Mapped[str] = mapped_column(Text, default="", comment="失败原因（成功时为空）")

    # 归因维度：无外键，理由见类 docstring
    space_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="所属空间 ID（可空）")
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="所属会话 ID（可空）")
    # 所属执行记录（agent_run.id）；同样不建外键，执行记录清理后成本历史需留存
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="所属执行记录 ID（可空）")

    # 路由与成本
    routing_tier: Mapped[str] = mapped_column(
        Text, default="", comment="smart-router 决策档位：SIMPLE/MEDIUM/COMPLEX/REASONING"
    )
    cost_usd: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="预估成本（美元）；模型未收录定价时为 NULL"
    )

    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    __table_args__ = (
        Index("idx_llm_log_model", "model_name"),
        Index("idx_llm_log_created", "created_at"),
        # 成本常按「空间/会话 + 时间」聚合，建复合索引
        Index("idx_llm_log_space", "space_id", "created_at"),
        Index("idx_llm_log_conversation", "conversation_id", "created_at"),
        Index("idx_llm_log_run", "run_id", "created_at"),
    )
