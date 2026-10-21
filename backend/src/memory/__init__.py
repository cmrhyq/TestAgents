"""记忆与知识库子系统对外接口，以及按配置装配的工厂。

工厂的职责只有一个：**根据配置决定「有没有向量能力」**。
配置关着就返回纯词法实现，上层代码不需要感知差异。
"""

from __future__ import annotations

from src.core.logging import get_logger
from src.memory.knowledge import CHUNK_OVERLAP, CHUNK_SIZE, KnowledgeBase, SearchHit, chunk_text
from src.memory.longterm import LongTermMemory

logger = get_logger(__name__)

__all__ = [
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "chunk_text",
    "SearchHit",
    "KnowledgeBase",
    "LongTermMemory",
    "get_long_term_memory",
    "get_knowledge_base",
    "reset_memory_singletons",
]

_long_term: LongTermMemory | None = None
_knowledge: KnowledgeBase | None = None


def get_long_term_memory() -> LongTermMemory:
    """全局跨会话记忆（无状态，可复用）。"""
    global _long_term
    if _long_term is None:
        _long_term = LongTermMemory()
    return _long_term


def get_knowledge_base(space_id: int | str | None = None) -> KnowledgeBase:
    """知识库实例。

    向量集合是按空间分的，带 space_id 时每次新建轻量壳（集合与 embedder 复用全局资源）；
    不带空间上下文时复用单例，走词法降级。
    """
    global _knowledge

    if space_id is not None:
        return _build(space_id)

    if _knowledge is None:
        _knowledge = _build(None)
    return _knowledge


def reset_memory_singletons() -> None:
    """重置单例（测试用）。"""
    global _long_term, _knowledge
    _long_term = None
    _knowledge = None


def _build(space_id: int | str | None) -> KnowledgeBase:
    """按配置装配知识库实例。"""
    from src.core.config import get_config

    config = get_config()
    store = None
    embedder = None

    if config.chroma.enabled and config.embedding.enabled and config.embedding.model:
        try:
            from src.memory.vector_store import ChromaVectorStore, litellm_embedder

            embedder = litellm_embedder(
                model=config.embedding.model,
                api_key=config.embedding.api_key,
                base_url=config.embedding.base_url,
            )
            if space_id is not None:
                store = ChromaVectorStore.for_space(space_id, embedder)
        except Exception as exc:
            logger.warning("向量能力装配失败，知识库降级为词法检索", error=str(exc))
            store = None
            embedder = None

    return KnowledgeBase(vector_store=store, embedder=embedder)
