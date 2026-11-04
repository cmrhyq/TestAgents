"""`KnowledgeBase` 的摄取、检索与管理。

向量库与 embedding 均注入替身，配合临时 SQLite 与临时工作区，不依赖外部服务。
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.data.models.base import Base
from src.memory.knowledge import KnowledgeBase
from src.workspace.manager import WorkspaceManager

SPACE_ID = 3001


@pytest.fixture()
def session_scope(tmp_path):
    """构造临时 SQLite 库，产出提交/回滚受控的 session 上下文管理器。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'kb.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _scope() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    yield _scope
    engine.dispose()


class FakeVectorStore:
    """最小向量库替身：按文本子串命中，记录调用。"""

    def __init__(self) -> None:
        self.documents: dict[str, str] = {}
        self.deleted: list[list[str]] = []

    def add(self, ids, documents, metadatas):
        for id_, doc in zip(ids, documents, strict=False):
            self.documents[id_] = doc

    def query(self, query_text, top_k):
        hits = [
            {"id": id_, "content": doc, "metadata": {}, "score": 0.9}
            for id_, doc in self.documents.items()
            if query_text in doc
        ]
        return hits[:top_k]

    def delete(self, ids):
        self.deleted.append(list(ids))
        for id_ in ids:
            self.documents.pop(id_, None)


def _embedder(texts: list[str]) -> list[list[float]]:
    """固定维度假向量：长度映射到第一维，用于断言调用发生了。"""
    return [[float(len(t)), 0.0, 0.0] for t in texts]


@pytest.fixture()
def lexical_kb(tmp_path, session_scope) -> KnowledgeBase:
    """无向量库（降级路径）。"""
    return KnowledgeBase(
        workspace=WorkspaceManager(root=tmp_path / "workspaces"),
        session_scope=session_scope,
        vector_store=None,
        embedder=None,
    )


@pytest.fixture()
def vector_kb(tmp_path, session_scope) -> KnowledgeBase:
    """带向量库与 embedder 的实例，走 vector 索引路径。"""
    return KnowledgeBase(
        workspace=WorkspaceManager(root=tmp_path / "workspaces"),
        session_scope=session_scope,
        vector_store=FakeVectorStore(),
        embedder=_embedder,
    )


class TestIngest:
    """文档摄取：落盘、切片、索引模式与非法输入。"""

    def test_writes_file_and_chunks(self, lexical_kb, tmp_path):
        doc = lexical_kb.ingest(SPACE_ID, "需求.md", "# 需求\n\n登录要支持短信验证码".encode())

        assert doc.status == "indexed"
        assert doc.chunk_count >= 1
        assert (tmp_path / "workspaces" / str(SPACE_ID) / "docs" / "需求.md").is_file()

    def test_lexical_mode_without_vector_store(self, lexical_kb):
        doc = lexical_kb.ingest(SPACE_ID, "a.md", "内容".encode())

        assert doc.index_mode == "lexical"

    def test_vector_mode_with_vector_store(self, vector_kb):
        doc = vector_kb.ingest(SPACE_ID, "b.md", "登录接口返回 token".encode())

        assert doc.index_mode == "vector"
        assert len(vector_kb.vector_store.documents) == doc.chunk_count

    def test_unsupported_suffix_rejected(self, lexical_kb):
        with pytest.raises(ValueError, match="不支持"):
            lexical_kb.ingest(SPACE_ID, "image.png", b"\x89PNG")

    def test_empty_file_rejected(self, lexical_kb):
        with pytest.raises(ValueError, match="为空"):
            lexical_kb.ingest(SPACE_ID, "empty.md", b"   ")

    def test_filename_with_path_is_sanitized(self, lexical_kb, tmp_path):
        doc = lexical_kb.ingest(SPACE_ID, "../../evil.md", "内容".encode())

        assert doc.filename == "evil.md"
        assert (tmp_path / "workspaces" / str(SPACE_ID) / "docs" / "evil.md").is_file()
        assert not (tmp_path / "workspaces" / "evil.md").exists()


class TestSearch:
    """检索：命中与未命中、空间隔离、top_k 上限。"""

    def test_lexical_search_finds_content(self, lexical_kb):
        lexical_kb.ingest(SPACE_ID, "api.md", "用户登录接口需要传 username 和 password".encode())

        hits = lexical_kb.search(SPACE_ID, "password")

        assert hits
        assert "password" in hits[0].content

    def test_lexical_search_misses_unrelated(self, lexical_kb):
        lexical_kb.ingest(SPACE_ID, "api.md", "用户登录接口".encode())

        assert lexical_kb.search(SPACE_ID, "完全不相关的内容") == []

    def test_vector_search_uses_store(self, vector_kb):
        vector_kb.ingest(SPACE_ID, "api.md", "订单查询接口返回订单列表".encode())

        hits = vector_kb.search(SPACE_ID, "订单查询")

        assert hits
        assert hits[0].document_name == "api.md"

    def test_space_isolation(self, lexical_kb):
        lexical_kb.ingest(SPACE_ID, "a.md", "空间 A 的机密内容".encode())

        assert lexical_kb.search(9999, "机密") == []

    def test_respects_top_k(self, lexical_kb):
        # 每段足够长，保证能切出多片
        paragraphs = "\n\n".join(f"关键词段落 {i} " + "填充内容" * 60 for i in range(20))
        lexical_kb.ingest(SPACE_ID, "many.md", paragraphs.encode())

        hits = lexical_kb.search(SPACE_ID, "关键词", top_k=3)

        assert len(hits) == 3


class TestManage:
    """文档列举、删除与重建索引。"""

    def test_list_documents(self, lexical_kb):
        lexical_kb.ingest(SPACE_ID, "a.md", "内容 A".encode())
        lexical_kb.ingest(SPACE_ID, "b.md", "内容 B".encode())

        names = [d.filename for d in lexical_kb.list_documents(SPACE_ID)]

        assert set(names) == {"a.md", "b.md"}

    def test_delete_removes_chunks_and_vectors(self, vector_kb):
        doc = vector_kb.ingest(SPACE_ID, "a.md", "会被删除的内容".encode())
        chunk_ids = [c.chroma_id for c in vector_kb.list_chunks(doc.id)]

        vector_kb.delete_document(doc.id)

        assert vector_kb.list_documents(SPACE_ID) == []
        assert vector_kb.search(SPACE_ID, "会被删除") == []
        assert vector_kb.vector_store.deleted and chunk_ids[0] in vector_kb.vector_store.deleted[0]

    def test_delete_unknown_is_noop(self, lexical_kb):
        lexical_kb.delete_document(999999)

    def test_reindex_rebuilds_chunks(self, lexical_kb, tmp_path):
        doc = lexical_kb.ingest(SPACE_ID, "a.md", "第一版内容".encode())

        # 磁盘上的文件被替换后重索引
        (tmp_path / "workspaces" / str(SPACE_ID) / "docs" / "a.md").write_text(
            "第二版内容", encoding="utf-8"
        )
        lexical_kb.reindex(doc.id)

        hits = lexical_kb.search(SPACE_ID, "第二版")
        assert hits
