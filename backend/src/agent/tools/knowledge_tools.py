"""知识库检索工具。

只暴露检索，不暴露写入：写入由人上传文档控制，避免污染检索质量。
"""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool, tool

from src.core.logging import get_logger
from src.memory.knowledge import KnowledgeBase

logger = get_logger(__name__)


def make_knowledge_tools(space_id: int | str, knowledge: KnowledgeBase | None = None) -> list[BaseTool]:
    """构造知识库检索工具。

    Args:
        space_id: 空间 ID，检索范围限定在该空间
        knowledge: 知识库实例；None 时使用全局实例

    Returns:
        工具列表：``knowledge_search``
    """
    kb = knowledge or _default_knowledge(space_id)

    @tool
    def knowledge_search(query: str, top_k: int = 5) -> str:
        """在当前空间的领域知识库里做语义检索（需求文档、接口文档、业务规则）。

        涉及业务语义时先检索，不要仅凭接口 schema 推断业务规则。命中时返回
        JSON 数组（document、seq、content、score），无命中时返回带 hits 与 note 的对象。

        Args:
            query: 检索问题或关键词
            top_k: 返回片段数，默认 5，最多 10
        """
        limit = max(1, min(int(top_k or 5), 10))
        try:
            hits = kb.search(space_id, query, top_k=limit)
        except Exception as exc:
            logger.error("知识库检索失败", space_id=str(space_id), error=str(exc))
            return json.dumps(
                {"error": str(exc), "hint": "知识库暂时不可用，可改用 read_file 直接读 docs/ 下的文件"},
                ensure_ascii=False,
            )

        if not hits:
            return json.dumps(
                {
                    "hits": [],
                    "note": "未检索到相关内容。若空间 docs/ 目录里有文档，可尝试换个关键词，或用 list_directory 看看有哪些文件。",
                },
                ensure_ascii=False,
            )

        return json.dumps([hit.to_dict() for hit in hits], ensure_ascii=False)

    return [knowledge_search]


def _default_knowledge(space_id: int | str) -> KnowledgeBase:
    """返回该空间的知识库实例。"""
    from src.memory import get_knowledge_base

    return get_knowledge_base(space_id)
