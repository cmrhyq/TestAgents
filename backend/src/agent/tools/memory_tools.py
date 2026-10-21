"""记忆工具：remember / recall / forget。

Agent 判断「这条信息以后还用得上」时自己调 ``remember``——这比在对话结束后
用 LLM 二次总结要可靠得多：让写记忆的人和做判断的人是同一个，它知道上下文。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from langchain_core.tools import BaseTool, tool

from src.core.logging import get_logger
from src.memory.longterm import VALID_CATEGORIES, LongTermMemory

logger = get_logger(__name__)


def make_memory_tools(
    space_id: int | str,
    conversation_id: int | None = None,
    memory: LongTermMemory | None = None,
) -> list[BaseTool]:
    """构造记忆读写工具（绑定空间与会话）。"""
    store = memory or _default_memory()

    @tool
    def recall(query: str = "") -> str:
        """检索当前空间的跨会话记忆。

        查历史结论、历史决策、已知问题、接口约定时使用。
        例如「之前有没有说过鉴权怎么取 token？」——先 recall 再回答，
        不要凭空猜测，也不要重复问用户已经说过的事。

        Args:
            query: 关键词；留空则返回最近的记忆条目
        """
        try:
            entries = store.recall(space_id, query)
        except Exception as exc:
            logger.error("记忆检索失败", error=str(exc))
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

        return json.dumps(
            [
                {
                    "id": entry.id,
                    "title": entry.title,
                    "content": entry.content,
                    "category": entry.category,
                    "tags": _load_tags(entry.tags),
                    "updated_at": entry.updated_at,
                }
                for entry in entries
            ],
            ensure_ascii=False,
        )

    @tool
    def remember(title: str, content: str, category: str = "fact", tags: str = "") -> str:
        """把一条值得长期记住的结论写入当前空间的跨会话记忆。

        **什么时候该用**：用户明确了约定（"我们统一用 v2 接口"）、你踩到了坑
        （"这个接口在 dev 环境一直 502"）、发现了业务规则（"金额单位是分不是元"）。
        **什么时候不该用**：一次性的执行结果、临时变量、用户随口说的话。

        Args:
            title: 一句话概括，作为列表标题
            content: 具体内容，包含足够的上下文以便未来直接使用
            category: fact(事实) / decision(决策) / preference(偏好) / issue(已知问题) / glossary(术语)
            tags: 逗号分隔的标签，如 "auth,token"
        """
        if category not in VALID_CATEGORIES:
            return json.dumps(
                {"error": f"非法 category: {category}，可选 {', '.join(VALID_CATEGORIES)}"},
                ensure_ascii=False,
            )

        tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
        try:
            entry = store.add(
                space_id,
                title=title,
                content=content,
                category=category,
                tags=tag_list,
                source_conversation_id=conversation_id,
            )
        except Exception as exc:
            logger.error("记忆写入失败", error=str(exc))
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

        return json.dumps(
            {"ok": True, "id": entry.id, "title": entry.title, "category": entry.category},
            ensure_ascii=False,
        )

    @tool
    def forget(memory_id: int) -> str:
        """删除一条已经过时或错误的记忆。

        当用户说「那条记错了」「已经不用了」，或你发现某条记忆与现实矛盾时使用。

        Args:
            memory_id: 记忆 ID，可从 recall 的结果里取
        """
        try:
            store.delete(memory_id)
        except Exception as exc:
            logger.error("记忆删除失败", error=str(exc))
            return json.dumps({"error": str(exc)}, ensure_ascii=False)
        return json.dumps({"ok": True, "deleted": memory_id}, ensure_ascii=False)

    return [recall, remember, forget]


def _load_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value: Any = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return [str(t) for t in value] if isinstance(value, list) else []


def _default_memory() -> LongTermMemory:
    from src.memory import get_long_term_memory

    return get_long_term_memory()
