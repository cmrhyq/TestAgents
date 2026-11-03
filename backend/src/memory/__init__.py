"""记忆与知识库子系统对外接口。

工厂按配置决定是否装配向量能力：配置关闭时返回纯词法实现，调用方无需感知差异。
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
    """返回全局跨会话记忆实例（无状态，可复用）。"""
    global _long_term
    if _long_term is None:
        _long_term = LongTermMemory()
    return _long_term


def get_knowledge_base(space_id: int | str | None = None) -> KnowledgeBase:
    """返回知识库实例。

    向量集合按空间划分：传入 space_id 时新建轻量壳并复用全局集合与 embedder；
    不传时复用单例，只能走词法检索。

    Args:
        space_id: 空间 ID；None 表示无空间上下文

    Returns:
        已按配置装配的知识库实例
    """
    global _knowledge

    if space_id is not None:
        return _build(space_id)

    if _knowledge is None:
        _knowledge = _build(None)
    return _knowledge


def reset_memory_singletons() -> None:
    """重置全局单例，仅供测试使用。"""
    global _long_term, _knowledge
    _long_term = None
    _knowledge = None


def _build(space_id: int | str | None) -> KnowledgeBase:
    """按配置装配知识库；向量能力装配失败时降级为词法检索并记录警告。"""
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
