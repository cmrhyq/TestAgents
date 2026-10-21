"""LLM 成本统计路由。

数据来自 ``llm_log``，按空间 / 会话 / 时间窗口聚合。

用法::

    GET /api/v1/usage/stats                         # 全站近 7 天
    GET /api/v1/usage/stats?space_id=123&days=30    # 某空间近 30 天
    GET /api/v1/usage/stats?conversation_id=456     # 单次对话花了多少
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.data.services.usage_service import DEFAULT_WINDOW_DAYS, MAX_WINDOW_DAYS, UsageService

router = APIRouter(tags=["用量统计"])


class GroupedUsage(BaseModel):
    """分组统计的一行（按模型或按路由档位）。"""

    key: str = Field(..., description="分组键：模型名 或 路由档位（未知为 unknown）")
    calls: int = Field(default=0, description="调用次数")
    total_tokens: int = Field(default=0, description="token 合计")
    cost_usd: float | None = Field(default=None, description="已知成本合计；全无定价时为 null")
    unpriced_calls: int = Field(default=0, description="成本未知的调用次数")


class UsageStats(BaseModel):
    """LLM 调用成本统计响应。"""

    days: int = Field(..., description="统计窗口（天）")
    space_id: str | None = Field(default=None, description="过滤的空间 ID")
    conversation_id: str | None = Field(default=None, description="过滤的会话 ID")

    total_calls: int = Field(default=0, description="调用总数")
    failed_calls: int = Field(default=0, description="失败次数")
    prompt_tokens: int = Field(default=0, description="输入 token 合计")
    completion_tokens: int = Field(default=0, description="输出 token 合计")
    total_tokens: int = Field(default=0, description="token 总计")

    cost_usd: float | None = Field(
        default=None,
        description="**已知**成本合计（美元）。为 null 表示窗口内没有任何一次调用能定价",
    )
    unpriced_calls: int = Field(
        default=0,
        description="成本未知的调用次数。cost_usd 不包含这些调用，勿当作全部成本",
    )

    by_model: list[GroupedUsage] = Field(default_factory=list, description="按实际命中模型分组")
    by_tier: list[GroupedUsage] = Field(default_factory=list, description="按路由档位分组")


@router.get(
    "/usage/stats",
    response_model=UsageStats,
    summary="LLM 调用成本统计",
    description=(
        "按空间/会话/时间窗口聚合 llm_log。\n\n"
        "注意 `cost_usd` 只累加有定价的调用；`unpriced_calls` 表示有多少次无法计价"
        "（如 litellm 定价表未收录的厂商）。两者要一起看。"
    ),
)
def get_usage_stats(
    space_id: int | None = Query(default=None, description="按空间过滤"),
    conversation_id: int | None = Query(default=None, description="按会话过滤"),
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=1, le=MAX_WINDOW_DAYS, description="统计窗口（天）"),
    session: Session = Depends(get_db),
) -> UsageStats:
    data = UsageService(session).stats(space_id=space_id, conversation_id=conversation_id, days=days)
    return UsageStats(**data)
