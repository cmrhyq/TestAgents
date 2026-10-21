from __future__ import annotations

from sqlalchemy import Float, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.base import Base, local_now
from src.utils.id import next_id


class LLMLog(Base):
    """LLM 调用记录表 - 统计每次大模型请求的 token 用量与使用模型。

    由 ``src.core.llm.llm_service.LLMService`` 在每次调用后写入
    （来源：litellm ``AIMessage.usage_metadata`` / ``response_metadata``）。

    **归因维度**：``space_id`` / ``conversation_id`` 让成本能按空间与会话聚合。
    这两列**刻意不建外键**——统计表要能挺过空间删除与会话清理，
    加 FK 会在删空间时把历史成本一起带走（或被 SET NULL 变成孤儿）。
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

    # ---- 归因维度（无外键，见类 docstring）----
    space_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="所属空间 ID（可空）")
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="所属会话 ID（可空）")

    # ---- 路由与成本 ----
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
        # 成本按「空间/会话 + 时间」聚合是最常见的查询形态，建复合索引
        Index("idx_llm_log_space", "space_id", "created_at"),
        Index("idx_llm_log_conversation", "conversation_id", "created_at"),
    )
