"""ChromaDB 向量库适配。

只实现 ``KnowledgeBase`` 需要的三个动作（add / query / delete），
把 Chroma 的 API 差异挡在这一层里。

**这个模块是可选的**：``chroma.enabled=false`` 时根本不会实例化它。
所以这里的代码不需要为「连不上」做兜底——连不上属于启用后的运行期故障，
由 ``KnowledgeBase.search`` 的降级逻辑处理。
"""

from __future__ import annotations

from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class ChromaVectorStore:
    """按空间分集合的向量库。

    集合命名：``space_knowledge_{space_id}``。一个空间一个集合，
    删除空间时可整集合删除，不需要逐条清理。
    """

    def __init__(self, collection: Any, embedder) -> None:
        self._collection = collection
        self._embedder = embedder

    @classmethod
    def for_space(cls, space_id: int | str, embedder) -> ChromaVectorStore:
        """按空间取（或建）集合。"""
        from src.core.chroma.chroma_manager import get_chroma_manager

        collection = get_chroma_manager().get_or_create_collection(
            name=collection_name(space_id),
            metadata={"space_id": str(space_id), "hnsw:space": "cosine"},
        )
        return cls(collection, embedder)

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        vectors = self._embedder(documents)
        if len(vectors) != len(ids):
            raise ValueError(f"向量数量与文档数量不一致: {len(vectors)} != {len(ids)}")
        self._collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=vectors)

    def query(self, query_text: str, top_k: int) -> list[dict[str, Any]]:
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
        if ids:
            self._collection.delete(ids=ids)


class ChromaCollectionVectorStore(ChromaVectorStore):
    """跨空间检索用的通用变体（集合由调用方决定）。"""


def collection_name(space_id: int | str) -> str:
    """知识库集合名。"""
    return f"space_knowledge_{space_id}"


def litellm_embedder(
    model: str,
    api_key: str = "",
    base_url: str = "",
) -> Any:
    """构造基于 litellm 的 embedding 函数。

    Args:
        model: litellm 格式模型名，如 ``zai/embedding-3``
        api_key: 密钥
        base_url: 自定义端点

    Returns:
        ``(texts: list[str]) -> list[list[float]]`` 形式的可调用对象
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
