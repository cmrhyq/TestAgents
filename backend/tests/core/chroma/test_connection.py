"""ChromaManager 单元测试。

使用 Mock 完全隔离外部 ChromaDB 服务依赖，覆盖：
- 单例模式
- 初始化流程（有/无认证）
- 连接检查
- 集合 CRUD
- 文档 CRUD
- LangChain VectorStore 集成
- 生命周期管理
- 便捷函数
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.chroma.chroma_manager import (
    ChromaManager,
    get_chroma_manager,
    init_chroma_from_config,
)
from src.core.config import ChromaConfig


@pytest.fixture(autouse=True)
def _reset_chroma_singleton():
    """每个测试前后重置 ChromaManager 单例，确保测试隔离。"""
    ChromaManager.reset_instance()
    yield
    ChromaManager.reset_instance()


@pytest.fixture()
def chroma_config() -> ChromaConfig:
    """测试用 ChromaConfig 实例。"""
    return ChromaConfig(
        host="test-host",
        port=9999,
        auth_credentials="test-token",
        auth_provider="chromadb.auth.token_authn.TokenAuthClientProvider",
        auth_token_transport_header="Authorization",
        tenant="test_tenant",
        database="test_database",
        default_collection="test_default",
    )


@pytest.fixture()
def chroma_config_no_auth() -> ChromaConfig:
    """无认证的 ChromaConfig 实例。"""
    return ChromaConfig(
        host="test-host",
        port=9999,
        auth_credentials="",
        tenant="test_tenant",
        database="test_database",
        default_collection="test_default",
    )


@pytest.fixture()
def mock_http_client():
    """Mock chromadb.HttpClient 构造函数，返回 mock client 实例。"""
    with patch("src.core.chroma.chroma_manager.chromadb.HttpClient") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


@pytest.fixture()
def initialized_manager(chroma_config, mock_http_client) -> ChromaManager:
    """已初始化的 ChromaManager 实例。"""
    manager = ChromaManager.get_instance()
    manager.initialize(chroma_config)
    return manager


@pytest.mark.unit
class TestChromaManagerSingleton:
    """单例模式测试。"""

    def test_get_instance_returns_same_object(self):
        instance_a = ChromaManager.get_instance()
        instance_b = ChromaManager.get_instance()
        assert instance_a is instance_b

    def test_reset_instance_clears_singleton(self):
        instance_a = ChromaManager.get_instance()
        ChromaManager.reset_instance()
        instance_b = ChromaManager.get_instance()
        assert instance_a is not instance_b


@pytest.mark.unit
class TestChromaManagerInitialize:
    """初始化流程测试。"""

    def test_initialize_creates_client(self, chroma_config, mock_http_client):
        manager = ChromaManager.get_instance()
        manager.initialize(chroma_config)

        assert manager._initialized is True
        assert manager._client is mock_http_client
        assert manager._config is chroma_config

    def test_initialize_skips_when_already_initialized(self, chroma_config, mock_http_client):
        manager = ChromaManager.get_instance()
        manager.initialize(chroma_config)
        manager.initialize(chroma_config)

        # HttpClient 只应被调用一次
        with patch("src.core.chroma.chroma_manager.chromadb.HttpClient") as mock_cls:
            manager.initialize(chroma_config)
            mock_cls.assert_not_called()

    def test_initialize_with_auth_credentials(self, chroma_config):
        with patch("src.core.chroma.chroma_manager.chromadb.HttpClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            manager = ChromaManager.get_instance()
            manager.initialize(chroma_config)

            call_kwargs = mock_cls.call_args[1]
            settings = call_kwargs["settings"]
            assert settings.chroma_client_auth_provider == chroma_config.auth_provider
            assert settings.chroma_client_auth_credentials == chroma_config.auth_credentials

    def test_initialize_without_auth_credentials(self, chroma_config_no_auth):
        with patch("src.core.chroma.chroma_manager.chromadb.HttpClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            manager = ChromaManager.get_instance()
            manager.initialize(chroma_config_no_auth)

            call_kwargs = mock_cls.call_args[1]
            settings = call_kwargs["settings"]
            assert (
                not hasattr(settings, "chroma_client_auth_credentials") or not settings.chroma_client_auth_credentials
            )


@pytest.mark.unit
class TestChromaManagerConnection:
    """连接检查测试。"""

    def test_check_connection_success(self, initialized_manager, mock_http_client):
        mock_http_client.heartbeat.return_value = 1234567890
        assert initialized_manager.check_connection() is True
        mock_http_client.heartbeat.assert_called_once()

    def test_check_connection_failure(self, initialized_manager, mock_http_client):
        mock_http_client.heartbeat.side_effect = ConnectionError("refused")
        assert initialized_manager.check_connection() is False

    def test_check_connection_not_initialized(self):
        manager = ChromaManager.get_instance()
        assert manager.check_connection() is False


@pytest.mark.unit
class TestChromaManagerCollections:
    """集合 CRUD 测试。"""

    def test_get_or_create_collection_with_name(self, initialized_manager, mock_http_client):
        mock_collection = MagicMock()
        mock_http_client.get_or_create_collection.return_value = mock_collection

        result = initialized_manager.get_or_create_collection("my_col")

        mock_http_client.get_or_create_collection.assert_called_once_with(name="my_col")
        assert result is mock_collection

    def test_get_or_create_collection_default_name(self, initialized_manager, mock_http_client):
        mock_collection = MagicMock()
        mock_http_client.get_or_create_collection.return_value = mock_collection

        result = initialized_manager.get_or_create_collection()

        mock_http_client.get_or_create_collection.assert_called_once_with(name="test_default")
        assert result is mock_collection

    def test_get_or_create_collection_with_metadata(self, initialized_manager, mock_http_client):
        mock_collection = MagicMock()
        mock_http_client.get_or_create_collection.return_value = mock_collection
        metadata = {"hnsw:space": "cosine"}

        initialized_manager.get_or_create_collection("my_col", metadata=metadata)

        mock_http_client.get_or_create_collection.assert_called_once_with(name="my_col", metadata=metadata)

    def test_get_collection(self, initialized_manager, mock_http_client):
        mock_collection = MagicMock()
        mock_http_client.get_collection.return_value = mock_collection

        result = initialized_manager.get_collection("existing_col")

        mock_http_client.get_collection.assert_called_once_with(name="existing_col")
        assert result is mock_collection

    def test_list_collections(self, initialized_manager, mock_http_client):
        mock_col_a = MagicMock()
        mock_col_a.name = "col_a"
        mock_col_b = MagicMock()
        mock_col_b.name = "col_b"
        mock_http_client.list_collections.return_value = [mock_col_a, mock_col_b]

        result = initialized_manager.list_collections()

        assert result == ["col_a", "col_b"]

    def test_list_collections_string_format(self, initialized_manager, mock_http_client):
        mock_http_client.list_collections.return_value = ["col_x", "col_y"]

        result = initialized_manager.list_collections()

        assert result == ["col_x", "col_y"]

    def test_delete_collection(self, initialized_manager, mock_http_client):
        initialized_manager.delete_collection("to_delete")

        mock_http_client.delete_collection.assert_called_once_with(name="to_delete")


@pytest.mark.unit
class TestChromaManagerDocuments:
    """文档 CRUD 测试。"""

    def test_add_documents(self, initialized_manager, mock_http_client):
        mock_collection = MagicMock()
        mock_http_client.get_or_create_collection.return_value = mock_collection

        initialized_manager.add_documents(
            collection_name="docs",
            documents=["text1", "text2"],
            metadatas=[{"k": "v1"}, {"k": "v2"}],
            ids=["id-1", "id-2"],
        )

        mock_collection.add.assert_called_once_with(
            documents=["text1", "text2"],
            metadatas=[{"k": "v1"}, {"k": "v2"}],
            ids=["id-1", "id-2"],
        )

    def test_add_documents_with_embeddings(self, initialized_manager, mock_http_client):
        mock_collection = MagicMock()
        mock_http_client.get_or_create_collection.return_value = mock_collection
        embeddings = [[0.1, 0.2], [0.3, 0.4]]

        initialized_manager.add_documents(
            collection_name="docs",
            documents=["text1", "text2"],
            ids=["id-1", "id-2"],
            embeddings=embeddings,
        )

        call_kwargs = mock_collection.add.call_args[1]
        assert call_kwargs["embeddings"] == embeddings

    def test_query_basic(self, initialized_manager, mock_http_client):
        mock_collection = MagicMock()
        mock_http_client.get_or_create_collection.return_value = mock_collection
        expected_results = {"ids": [["id-1"]], "documents": [["text1"]]}
        mock_collection.query.return_value = expected_results

        results = initialized_manager.query(
            query_texts=["search term"],
            collection_name="docs",
            n_results=5,
        )

        mock_collection.query.assert_called_once_with(
            query_texts=["search term"],
            n_results=5,
        )
        assert results == expected_results

    def test_query_with_where_filter(self, initialized_manager, mock_http_client):
        mock_collection = MagicMock()
        mock_http_client.get_or_create_collection.return_value = mock_collection
        mock_collection.query.return_value = {"ids": [[]]}
        where_filter = {"source": "api"}

        initialized_manager.query(
            query_texts=["q"],
            collection_name="docs",
            where=where_filter,
        )

        call_kwargs = mock_collection.query.call_args[1]
        assert call_kwargs["where"] == where_filter

    def test_query_with_include(self, initialized_manager, mock_http_client):
        mock_collection = MagicMock()
        mock_http_client.get_or_create_collection.return_value = mock_collection
        mock_collection.query.return_value = {"ids": [[]]}
        include_fields = ["metadatas", "documents", "distances"]

        initialized_manager.query(
            query_texts=["q"],
            collection_name="docs",
            include=include_fields,
        )

        call_kwargs = mock_collection.query.call_args[1]
        assert call_kwargs["include"] == include_fields

    def test_update_documents(self, initialized_manager, mock_http_client):
        mock_collection = MagicMock()
        mock_http_client.get_or_create_collection.return_value = mock_collection

        initialized_manager.update_documents(
            ids=["id-1"],
            collection_name="docs",
            documents=["updated text"],
            metadatas=[{"k": "new_v"}],
        )

        mock_collection.update.assert_called_once_with(
            ids=["id-1"],
            documents=["updated text"],
            metadatas=[{"k": "new_v"}],
        )

    def test_delete_documents(self, initialized_manager, mock_http_client):
        mock_collection = MagicMock()
        mock_http_client.get_or_create_collection.return_value = mock_collection

        initialized_manager.delete_documents(
            ids=["id-1", "id-2"],
            collection_name="docs",
        )

        mock_collection.delete.assert_called_once_with(ids=["id-1", "id-2"])


@pytest.mark.unit
class TestChromaManagerVectorStore:
    """LangChain VectorStore 集成测试。"""

    def test_get_vector_store(self, initialized_manager):
        mock_embedding = MagicMock()

        with patch("src.core.chroma.chroma_manager.Chroma") as mock_chroma_cls:
            mock_store = MagicMock()
            mock_chroma_cls.return_value = mock_store

            result = initialized_manager.get_vector_store(
                embedding_function=mock_embedding,
                collection_name="vs_col",
            )

            mock_chroma_cls.assert_called_once_with(
                client=initialized_manager._client,
                collection_name="vs_col",
                embedding_function=mock_embedding,
            )
            assert result is mock_store

    def test_get_vector_store_default_collection(self, initialized_manager):
        mock_embedding = MagicMock()

        with patch("src.core.chroma.chroma_manager.Chroma") as mock_chroma_cls:
            mock_chroma_cls.return_value = MagicMock()

            initialized_manager.get_vector_store(embedding_function=mock_embedding)

            call_kwargs = mock_chroma_cls.call_args[1]
            assert call_kwargs["collection_name"] == "test_default"


@pytest.mark.unit
class TestChromaManagerLifecycle:
    """生命周期管理测试。"""

    def test_close_resets_state(self, initialized_manager):
        assert initialized_manager._initialized is True

        initialized_manager.close()

        assert initialized_manager._initialized is False
        assert initialized_manager._client is None
        assert initialized_manager._config is None

    def test_client_property_raises_when_not_initialized(self):
        manager = ChromaManager.get_instance()

        with pytest.raises(RuntimeError, match="ChromaDB 尚未初始化"):
            _ = manager.client

    def test_operations_raise_when_not_initialized(self):
        manager = ChromaManager.get_instance()

        with pytest.raises(RuntimeError, match="ChromaDB 尚未初始化"):
            manager.get_or_create_collection("col")

        with pytest.raises(RuntimeError, match="ChromaDB 尚未初始化"):
            manager.get_collection("col")

        with pytest.raises(RuntimeError, match="ChromaDB 尚未初始化"):
            manager.list_collections()

        with pytest.raises(RuntimeError, match="ChromaDB 尚未初始化"):
            manager.delete_collection("col")

        with pytest.raises(RuntimeError, match="ChromaDB 尚未初始化"):
            manager.get_vector_store(embedding_function=MagicMock())


@pytest.mark.unit
class TestConvenienceFunctions:
    """便捷函数测试。"""

    def test_get_chroma_manager(self):
        manager = get_chroma_manager()
        assert isinstance(manager, ChromaManager)
        assert manager is ChromaManager.get_instance()

    def test_init_chroma_from_config(self, chroma_config, mock_http_client):
        manager = init_chroma_from_config(chroma_config)

        assert isinstance(manager, ChromaManager)
        assert manager._initialized is True
        assert manager._config is chroma_config
