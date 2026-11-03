"""LLM 调用成本统计，数据源为 ``llm_log``。

``cost_usd`` 是已知成本合计（SQL 聚合跳过 NULL），未定价调用次数见 ``unpriced_calls``；
``llm_log`` 的 ``space_id`` / ``conversation_id`` 无外键，空间删除后统计仍保留。
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
        """绑定只读会话。

        Args:
            session: 调用方持有的会话，本服务只读不写
        """
        self._session = session

    def stats(
        self,
        *,
        space_id: int | None = None,
        conversation_id: int | None = None,
        days: int = DEFAULT_WINDOW_DAYS,
    ) -> dict[str, Any]:
        """按时间窗口聚合调用次数、token 与成本。

        Args:
            space_id: 限定空间；None 表示全部空间
            conversation_id: 限定会话；None 表示全部会话
            days: 时间窗口天数，近期数据按 ``created_at`` 下限过滤

        Returns:
            聚合结果字典，含总数、按模型与按路由档位的分组；无定价数据时
            ``cost_usd`` 为 None，对应调用计入 ``unpriced_calls``
        """
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
        """按指定列分组统计调用数、token 与成本，按调用数倒序。

        Args:
            column: 分组列，如 ``LLMLog.model_name``
            conditions: 过滤条件
            skip_empty: 是否跳过分组键为空字符串的行

        Returns:
            分组结果列表；分组键为空时以 ``unknown`` 呈现
        """
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
    """返回时间窗口起点。

    格式与 ``local_now`` 一致（毫秒精度 ISO 字符串），字符串比较才等价于时间比较。

    Args:
        days: 回溯天数

    Returns:
        时间窗口下界字符串
    """
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
