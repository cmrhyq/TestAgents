"""ChromaDB 向量库适配。

仅实现 ``KnowledgeBase`` 需要的 add / query / delete 三个动作，隔离 Chroma 的 API 差异。
本模块可选：``chroma.enabled=false`` 时不会实例化，连接失败由 ``KnowledgeBase.search`` 降级处理。
"""

from __future__ import annotations

from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class ChromaVectorStore:
    """按空间划分集合的向量库。

    集合名为 ``space_knowledge_{space_id}``，删除空间时可整集合删除。

    Args:
        collection: Chroma 集合对象
        embedder: 文本向量化函数，签名 ``(list[str]) -> list[list[float]]``
    """

    def __init__(self, collection: Any, embedder) -> None:
        self._collection = collection
        self._embedder = embedder

    @classmethod
    def for_space(cls, space_id: int | str, embedder) -> ChromaVectorStore:
        """取或创建空间对应的集合，距离度量固定为 cosine。"""
        from src.core.chroma.chroma_manager import get_chroma_manager

        collection = get_chroma_manager().get_or_create_collection(
            name=collection_name(space_id),
            metadata={"space_id": str(space_id), "hnsw:space": "cosine"},
        )
        return cls(collection, embedder)

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        """写入向量与原文，会调用 embedder。

        Raises:
            ValueError: 向量数量与 ``ids`` 数量不一致
        """
        vectors = self._embedder(documents)
        if len(vectors) != len(ids):
            raise ValueError(f"向量数量与文档数量不一致: {len(vectors)} != {len(ids)}")
        self._collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=vectors)

    def query(self, query_text: str, top_k: int) -> list[dict[str, Any]]:
        """按相似度检索，返回 ``id`` / ``content`` / ``metadata`` / ``score`` 列表。"""
        vector = self._embedder([query_text])[0]
        result = self._collection.query(
            query_embeddings=[vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        hits: list[dict[str, Any]] = []
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        for index, id_ in enumerate(ids):
            distance = distances[index] if index < len(distances) else 1.0
            hits.append(
                {
                    "id": id_,
                    "content": documents[index] if index < len(documents) else "",
                    "metadata": metadatas[index] if index < len(metadatas) else {},
                    # cosine 距离转相似度：距离越小越相似
                    "score": max(0.0, 1.0 - float(distance)),
                }
            )
        return hits

    def delete(self, ids: list[str]) -> None:
        """按 ID 删除向量；``ids`` 为空时不发起调用。"""
        if ids:
            self._collection.delete(ids=ids)


class ChromaCollectionVectorStore(ChromaVectorStore):
    """集合由调用方指定的变体，用于跨空间检索。"""


def collection_name(space_id: int | str) -> str:
    """返回空间对应的集合名。"""
    return f"space_knowledge_{space_id}"


def litellm_embedder(
    model: str,
    api_key: str = "",
    base_url: str = "",
) -> Any:
    """构造基于 litellm 的 embedding 函数。

    返回的函数每次调用都会发起一次远程请求，调用方需自行控制批量与重试。

    Args:
        model: litellm 格式模型名
        api_key: 密钥；为空时使用 litellm 的环境变量配置
        base_url: 自定义端点；为空时使用模型默认端点

    Returns:
        签名为 ``(list[str]) -> list[list[float]]`` 的可调用对象
    """

    def _embed(texts: list[str]) -> list[list[float]]:
        import litellm

        kwargs: dict[str, Any] = {"model": model, "input": texts}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["api_base"] = base_url

        response = litellm.embedding(**kwargs)
        return [item["embedding"] for item in response.data]

    return _embed
