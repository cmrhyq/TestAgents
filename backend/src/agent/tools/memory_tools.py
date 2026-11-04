"""记忆工具：``remember`` / ``recall`` / ``forget``。

记忆由 Agent 在对话中自行写入：写入者与判断者是同一方，比事后二次总结可靠。
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
    """构造记忆读写工具（绑定空间与会话）。

    Args:
        space_id: 空间 ID，记忆按空间隔离
        conversation_id: 会话 ID，写入时记录来源
        memory: 长期记忆实例；None 时使用全局实例

    Returns:
        工具列表：``recall``、``remember``、``forget``
    """
    store = memory or _default_memory()

    @tool
    def recall(query: str = "") -> str:
        """检索当前空间的跨会话记忆。

        用于查询历史结论、历史决策、已知问题与接口约定；先检索再回答，
        避免重复询问用户已说明过的信息。

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
        """把一条长期有效的结论写入当前空间的跨会话记忆。

        副作用：写入记忆库。适用于用户明确的约定、已踩过的坑、业务规则；
        不适用于一次性执行结果、临时变量与闲聊内容。

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

        副作用：删除记忆库中的记录。

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
    """解析记忆的标签 JSON；非法或非列表时返回空列表。"""
    if not raw:
        return []
    try:
        value: Any = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return [str(t) for t in value] if isinstance(value, list) else []


def _default_memory() -> LongTermMemory:
    """返回全局长期记忆实例。"""
    from src.memory import get_long_term_memory

    return get_long_term_memory()
