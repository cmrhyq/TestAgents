"""ChromaDB 向量数据库连接管理。

提供 HttpClient 连接、集合与文档 CRUD，以及与 LangChain ``Chroma`` 的集成入口。
"""

import threading
from typing import Any, Optional

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.api.types import QueryResult
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from src.core.config import ChromaConfig, get_config
from src.core.logging import get_logger

logger = get_logger(__name__)


class ChromaManager:
    """ChromaDB 连接管理器单例。

    ``initialize`` 只生效一次，重复调用直接返回；未初始化时访问客户端会抛 ``RuntimeError``。
    """

    _instance: Optional["ChromaManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._client: chromadb.ClientAPI | None = None
        self._config: ChromaConfig | None = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "ChromaManager":
        """返回单例实例，以双重检查锁创建。

        Returns:
            全局唯一的管理器实例
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def initialize(self, config: ChromaConfig | None = None) -> None:
        """建立 ChromaDB HttpClient 连接，重复调用直接返回。

        副作用：创建到 ChromaDB 服务的长连接。

        Args:
            config: ChromaDB 配置；None 时取全局配置
        """
        if self._initialized:
            logger.debug("ChromaDB 已初始化，跳过重复初始化")
            return

        if config is None:
            config = get_config().chroma

        self._config = config

        settings = self._build_settings(config)
        self._client = chromadb.HttpClient(
            host=config.host,
            port=config.port,
            tenant=config.tenant,
            database=config.database,
            settings=settings,
        )

        self._initialized = True
        logger.info(
            "ChromaDB 初始化完成",
            host=config.host,
            port=config.port,
            tenant=config.tenant,
            database=config.database,
        )

    @staticmethod
    def _build_settings(config: ChromaConfig) -> Settings:
        """按配置构建 ``Settings``，仅在填写凭证时启用 Token 认证。

        Args:
            config: ChromaDB 配置

        Returns:
            chromadb ``Settings`` 对象
        """
        if config.auth_credentials:
            return Settings(
                chroma_client_auth_provider=config.auth_provider,
                chroma_client_auth_credentials=config.auth_credentials,
                chroma_auth_token_transport_header=config.auth_token_transport_header,
            )
        return Settings()

    def check_connection(self) -> bool:
        """通过 ``heartbeat`` 探测服务可用性。

        Returns:
            可用为 True；异常或未初始化时返回 False
        """
        try:
            self._check_initialized()
            self._client.heartbeat()  # type: ignore[union-attr]
            return True
        except Exception as e:
            logger.error("ChromaDB 连接检查失败", error=str(e))
            return False

    # 集合 CRUD

    def get_or_create_collection(
        self,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Collection:
        """获取集合，不存在时创建。

        副作用：可能在建库侧新建集合。

        Args:
            name: 集合名称；None 时取配置的默认集合
            metadata: 集合元数据

        Returns:
            ChromaDB 集合对象
        """
        self._check_initialized()
        collection_name = name or self._config.default_collection  # type: ignore[union-attr]
        kwargs: dict[str, Any] = {"name": collection_name}
        if metadata:
            kwargs["metadata"] = metadata
        collection = self._client.get_or_create_collection(**kwargs)  # type: ignore[union-attr]
        logger.debug("获取/创建集合", collection=collection_name)
        return collection

    def get_collection(self, name: str) -> Collection:
        """获取已存在的集合。

        Args:
            name: 集合名称

        Returns:
            ChromaDB 集合对象

        Raises:
            ValueError: 集合不存在
        """
        self._check_initialized()
        collection = self._client.get_collection(name=name)  # type: ignore[union-attr]
        return collection

    def list_collections(self) -> list[str]:
        """列出所有集合名称。

        Returns:
            集合名称列表；兼容返回字符串或集合对象的客户端版本
        """
        self._check_initialized()
        collections = self._client.list_collections()  # type: ignore[union-attr]
        return [c if isinstance(c, str) else c.name for c in collections]

    def delete_collection(self, name: str) -> None:
        """删除集合及其全部文档。

        副作用：数据不可恢复。

        Args:
            name: 集合名称
        """
        self._check_initialized()
        self._client.delete_collection(name=name)  # type: ignore[union-attr]
        logger.info("集合已删除", collection=name)

    # 文档 CRUD

    def add_documents(
        self,
        collection_name: str | None = None,
        documents: list[str] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
        embeddings: list[list[float]] | None = None,
    ) -> None:
        """向集合追加文档，集合不存在时先创建。

        副作用：写入向量库。

        Args:
            collection_name: 集合名称；None 时取默认集合
            documents: 文档文本列表
            metadatas: 与 documents 等长的元数据列表
            ids: 与 documents 等长的文档 ID 列表
            embeddings: 预计算向量；缺省时由集合的嵌入函数生成
        """
        collection = self.get_or_create_collection(collection_name)
        kwargs: dict[str, Any] = {}
        if documents:
            kwargs["documents"] = documents
        if metadatas:
            kwargs["metadatas"] = metadatas
        if ids:
            kwargs["ids"] = ids
        if embeddings:
            kwargs["embeddings"] = embeddings
        collection.add(**kwargs)
        logger.info(
            "文档已添加",
            collection=collection.name,
            count=len(ids) if ids else 0,
        )

    def query(
        self,
        query_texts: list[str],
        collection_name: str | None = None,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> QueryResult:
        """按文本相似度查询集合。

        副作用：集合不存在时会被创建。

        Args:
            query_texts: 查询文本列表
            collection_name: 集合名称；None 时取默认集合
            n_results: 每个查询返回的结果数
            where: 元数据过滤条件
            include: 返回字段，取值如 ``metadatas`` / ``documents`` / ``distances``

        Returns:
            ChromaDB 查询结果
        """
        collection = self.get_or_create_collection(collection_name)
        kwargs: dict[str, Any] = {
            "query_texts": query_texts,
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        if include:
            kwargs["include"] = include
        results = collection.query(**kwargs)
        return results

    def update_documents(
        self,
        ids: list[str],
        collection_name: str | None = None,
        documents: list[str] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
        embeddings: list[list[float]] | None = None,
    ) -> None:
        """按 ID 覆盖文档内容。

        副作用：写入向量库；集合不存在时会被创建。

        Args:
            ids: 待更新的文档 ID 列表
            collection_name: 集合名称；None 时取默认集合
            documents: 新的文档文本
            metadatas: 新的元数据
            embeddings: 新的向量
        """
        collection = self.get_or_create_collection(collection_name)
        kwargs: dict[str, Any] = {"ids": ids}
        if documents:
            kwargs["documents"] = documents
        if metadatas:
            kwargs["metadatas"] = metadatas
        if embeddings:
            kwargs["embeddings"] = embeddings
        collection.update(**kwargs)
        logger.info("文档已更新", collection=collection.name, count=len(ids))

    def delete_documents(
        self,
        ids: list[str],
        collection_name: str | None = None,
    ) -> None:
        """按 ID 删除文档。

        副作用：写入向量库；集合不存在时会被创建。

        Args:
            ids: 待删除的文档 ID 列表
            collection_name: 集合名称；None 时取默认集合
        """
        collection = self.get_or_create_collection(collection_name)
        collection.delete(ids=ids)
        logger.info("文档已删除", collection=collection.name, count=len(ids))

    # LangChain 集成

    def get_vector_store(
        self,
        embedding_function: Embeddings,
        collection_name: str | None = None,
    ) -> Chroma:
        """构造复用当前连接的 LangChain ``Chroma`` 实例。

        Args:
            embedding_function: LangChain Embeddings 实例
            collection_name: 集合名称；None 时取默认集合

        Returns:
            LangChain VectorStore
        """
        self._check_initialized()
        name = collection_name or self._config.default_collection  # type: ignore[union-attr]
        return Chroma(
            client=self._client,
            collection_name=name,
            embedding_function=embedding_function,
        )

    # 生命周期

    @property
    def client(self) -> chromadb.ClientAPI:
        """返回底层 chromadb HttpClient。

        Raises:
            RuntimeError: 尚未初始化
        """
        self._check_initialized()
        return self._client  # type: ignore[return-value]

    def close(self) -> None:
        """释放客户端引用并回到未初始化状态。"""
        self._client = None
        self._config = None
        self._initialized = False
        logger.info("ChromaDB 连接已关闭")

    def _check_initialized(self) -> None:
        """校验初始化状态，未初始化时抛出 ``RuntimeError``。

        Raises:
            RuntimeError: 客户端尚未创建
        """
        if not self._initialized:
            raise RuntimeError("ChromaDB 尚未初始化，请先调用 ChromaManager.get_instance().initialize()")

    @classmethod
    def reset_instance(cls) -> None:
        """销毁单例实例，仅供测试使用。

        副作用：先关闭现有客户端。
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None


def get_chroma_manager() -> ChromaManager:
    """返回 ChromaDB 管理器单例。

    Returns:
        全局唯一的管理器实例
    """
    return ChromaManager.get_instance()


def init_chroma_from_config(config: ChromaConfig | None = None) -> ChromaManager:
    """按配置初始化 ChromaDB 连接。

    副作用：建立到 ChromaDB 服务的连接。

    Args:
        config: ChromaDB 配置；None 时取全局配置

    Returns:
        已初始化的管理器实例
    """
    manager = get_chroma_manager()
    manager.initialize(config)
    return manager
