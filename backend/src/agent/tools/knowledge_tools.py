"""知识库检索工具。

只暴露检索，不暴露写入——「往知识库里塞什么」应当由人决定（上传文档），
让 Agent 自己往知识库写会迅速污染检索质量。
"""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool, tool

from src.core.logging import get_logger
from src.memory.knowledge import KnowledgeBase

logger = get_logger(__name__)


def make_knowledge_tools(space_id: int | str, knowledge: KnowledgeBase | None = None) -> list[BaseTool]:
    """构造知识库检索工具。"""
    kb = knowledge or _default_knowledge(space_id)

    @tool
    def knowledge_search(query: str, top_k: int = 5) -> str:
        """在当前空间的领域知识库里做语义检索（需求文档、接口文档、业务规则）。

        回答业务语义问题前先查一遍，不要凭接口 schema 猜业务规则。
        返回 JSON 数组，每项含 document（文档名）、seq（片段序号）、content（正文）、score（相关度）。

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
    from src.memory import get_knowledge_base

    return get_knowledge_base(space_id)
