"""LLM 调用成本统计。

数据源是 ``llm_log``（由 ``LLMService`` 在每次调用后写入）。

两个刻意的设计：

1. **成本未知 ≠ 成本为 0**。``sum(cost_usd)`` 在 SQL 里会跳过 NULL，
   所以 ``cost_usd`` 表示「**已知**成本合计」；另给 ``unpriced_calls``
   告诉调用方有多少次调用没有定价。只看总额会被误读成「全部成本」。
2. **按空间/会话归因**依赖 ``llm_log.space_id`` / ``conversation_id``。
   这两列没有外键，空间删除后统计仍保留——成本是要对账的，不该随业务数据消失。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from src.data.models.llm_log import LLMLog

DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 365


class UsageService:
    """按空间 / 会话 / 时间窗口聚合 LLM 调用成本。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def stats(
        self,
        *,
        space_id: int | None = None,
        conversation_id: int | None = None,
        days: int = DEFAULT_WINDOW_DAYS,
    ) -> dict[str, Any]:
        """返回聚合结果（结构与 API 响应对应）。"""
        conditions = [LLMLog.created_at >= _since(days)]
        if space_id is not None:
            conditions.append(LLMLog.space_id == space_id)
        if conversation_id is not None:
            conditions.append(LLMLog.conversation_id == conversation_id)

        total_calls, failed_calls, prompt, completion, total, cost, unpriced = self._session.execute(
            select(
                func.count(LLMLog.id),
                func.coalesce(func.sum(case((LLMLog.success == 0, 1), else_=0)), 0),
                func.coalesce(func.sum(LLMLog.prompt_tokens), 0),
                func.coalesce(func.sum(LLMLog.completion_tokens), 0),
                func.coalesce(func.sum(LLMLog.total_tokens), 0),
                func.sum(LLMLog.cost_usd),
                func.coalesce(func.sum(case((LLMLog.cost_usd.is_(None), 1), else_=0)), 0),
            ).where(*conditions)
        ).one()

        return {
            "days": days,
            "space_id": str(space_id) if space_id is not None else None,
            "conversation_id": str(conversation_id) if conversation_id is not None else None,
            "total_calls": int(total_calls or 0),
            "failed_calls": int(failed_calls or 0),
            "prompt_tokens": int(prompt or 0),
            "completion_tokens": int(completion or 0),
            "total_tokens": int(total or 0),
            "cost_usd": round(float(cost), 8) if cost is not None else None,
            "unpriced_calls": int(unpriced or 0),
            "by_model": self._group_by(LLMLog.model_name, conditions),
            "by_tier": self._group_by(LLMLog.routing_tier, conditions, skip_empty=True),
        }

    def _group_by(
        self,
        column: Any,
        conditions: list[Any],
        *,
        skip_empty: bool = False,
    ) -> list[dict[str, Any]]:
        """按某一列分组统计（模型 / 路由档位）。"""
        stmt: Select[Any] = (
            select(
                column,
                func.count(LLMLog.id),
                func.coalesce(func.sum(LLMLog.total_tokens), 0),
                func.sum(LLMLog.cost_usd),
                func.coalesce(func.sum(case((LLMLog.cost_usd.is_(None), 1), else_=0)), 0),
            )
            .where(*conditions)
            .group_by(column)
            .order_by(func.count(LLMLog.id).desc())
        )

        rows = self._session.execute(stmt).all()
        result = []
        for key, calls, tokens, cost, unpriced in rows:
            label = key if isinstance(key, str) else ""
            if skip_empty and not label:
                continue
            result.append(
                {
                    "key": label or "unknown",
                    "calls": int(calls or 0),
                    "total_tokens": int(tokens or 0),
                    "cost_usd": round(float(cost), 8) if cost is not None else None,
                    "unpriced_calls": int(unpriced or 0),
                }
            )
        return result


def _since(days: int) -> str:
    """时间窗口起点（与 ``local_now`` 同格式，保证字符串比较等价于时间比较）。"""
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
