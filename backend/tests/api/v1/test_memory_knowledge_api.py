"""记忆与知识库 API 测试。

覆盖：记忆 CRUD + 镜像同步、文档上传 + 列表 + 切片 + 检索 + 删除。
记忆/知识库实例绑定到临时库与临时工作目录。
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.deps import get_db
from src.api.v1 import knowledge as knowledge_api
from src.api.v1 import memory as memory_api
from src.data.models.base import Base
from src.memory.knowledge import KnowledgeBase
from src.memory.longterm import LongTermMemory
from src.workspace.manager import WorkspaceManager

SPACE_ID = 8080


@pytest.fixture()
def client(tmp_path) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _scope():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _get_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    workspace = WorkspaceManager(root=tmp_path / "workspaces")
    workspace.create(SPACE_ID, "知识库空间")
    with _scope() as session:
        from src.data.models.space import Space

        session.add(Space(id=SPACE_ID, name="知识库空间", workspace_path=f"workspaces/{SPACE_ID}"))

    long_term = LongTermMemory(workspace=workspace, session_scope=_scope)
    kb = KnowledgeBase(workspace=workspace, session_scope=_scope)

    prev_lt = memory_api.get_long_term_memory
    prev_kb = knowledge_api.get_knowledge_base
    memory_api.get_long_term_memory = lambda: long_term
    knowledge_api.get_knowledge_base = lambda space_id=None: kb

    from app import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = _get_db
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()
        memory_api.get_long_term_memory = prev_lt
        knowledge_api.get_knowledge_base = prev_kb
        engine.dispose()


class TestMemoryApi:
    def test_create_and_list(self, client):
        created = client.post(
            f"/api/v1/spaces/{SPACE_ID}/memories",
            json={"title": "鉴权约定", "content": "所有接口用 Bearer token", "category": "decision", "tags": ["auth"]},
        )
        assert created.status_code == 201, created.text

        listed = client.get(f"/api/v1/spaces/{SPACE_ID}/memories")
        assert listed.status_code == 200
        assert listed.json()["total"] == 1
        item = listed.json()["items"][0]
        assert item["title"] == "鉴权约定"
        assert item["category_label"] == "决策"
        assert item["tags"] == ["auth"]

    def test_update(self, client):
        created = client.post(
            f"/api/v1/spaces/{SPACE_ID}/memories", json={"title": "旧", "content": "a"}
        ).json()

        updated = client.put(f"/api/v1/memories/{created['id']}", json={"title": "新", "content": "b"})

        assert updated.status_code == 200
        assert updated.json()["title"] == "新"
        assert updated.json()["content"] == "b"

    def test_soft_delete_hides_from_list(self, client):
        created = client.post(
            f"/api/v1/spaces/{SPACE_ID}/memories", json={"title": "待删", "content": "x"}
        ).json()

        assert client.delete(f"/api/v1/memories/{created['id']}").status_code == 204

        assert client.get(f"/api/v1/spaces/{SPACE_ID}/memories").json()["total"] == 0

    def test_invalid_category_rejected(self, client):
        response = client.post(
            f"/api/v1/spaces/{SPACE_ID}/memories", json={"title": "t", "category": "nonsense"}
        )
        assert response.status_code == 422

    def test_unknown_memory_404(self, client):
        assert client.put("/api/v1/memories/999999", json={"title": "x"}).status_code == 404

    def test_sync_writes_markdown(self, client, tmp_path):
        client.post(f"/api/v1/spaces/{SPACE_ID}/memories", json={"title": "写入镜像", "content": "内容"})

        response = client.post(f"/api/v1/spaces/{SPACE_ID}/memories/sync")

        assert response.status_code == 200
        mirror = tmp_path / "workspaces" / str(SPACE_ID) / "memory" / "MEMORY.md"
        assert "写入镜像" in mirror.read_text(encoding="utf-8")


class TestKnowledgeApi:
    def test_upload_and_list(self, client, tmp_path):
        response = client.post(
            f"/api/v1/spaces/{SPACE_ID}/documents",
            files={"file": ("需求.md", "登录接口需要短信验证码".encode(), "text/markdown")},
        )

        assert response.status_code == 201, response.text
        doc = response.json()
        assert doc["filename"] == "需求.md"
        assert doc["status"] == "indexed"
        assert doc["index_mode"] == "lexical"
        assert (tmp_path / "workspaces" / str(SPACE_ID) / "docs" / "需求.md").is_file()

        listed = client.get(f"/api/v1/spaces/{SPACE_ID}/documents").json()
        assert listed["total"] == 1
        assert listed["vector_enabled"] is False

    def test_upload_rejects_unsupported_type(self, client):
        response = client.post(
            f"/api/v1/spaces/{SPACE_ID}/documents",
            files={"file": ("a.png", b"\x89PNG", "image/png")},
        )
        assert response.status_code == 422

    def test_chunks_endpoint(self, client):
        doc = client.post(
            f"/api/v1/spaces/{SPACE_ID}/documents",
            files={"file": ("a.md", "第一段内容".encode(), "text/markdown")},
        ).json()

        chunks = client.get(f"/api/v1/documents/{doc['id']}/chunks")

        assert chunks.status_code == 200
        assert chunks.json()[0]["content"].startswith("第一段")

    def test_search_preview(self, client):
        client.post(
            f"/api/v1/spaces/{SPACE_ID}/documents",
            files={"file": ("a.md", "订单查询接口返回订单列表".encode(), "text/markdown")},
        )

        response = client.post(
            f"/api/v1/spaces/{SPACE_ID}/documents/search", json={"query": "订单查询", "top_k": 3}
        )

        assert response.status_code == 200
        assert response.json()["hits"]
        assert response.json()["vector_enabled"] is False

    def test_delete_document(self, client, tmp_path):
        doc = client.post(
            f"/api/v1/spaces/{SPACE_ID}/documents",
            files={"file": ("a.md", "内容".encode(), "text/markdown")},
        ).json()

        assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 204

        assert client.get(f"/api/v1/spaces/{SPACE_ID}/documents").json()["total"] == 0
        assert not (tmp_path / "workspaces" / str(SPACE_ID) / "docs" / "a.md").exists()

    def test_reindex_after_file_change(self, client, tmp_path):
        doc = client.post(
            f"/api/v1/spaces/{SPACE_ID}/documents",
            files={"file": ("a.md", "第一版".encode(), "text/markdown")},
        ).json()
        (tmp_path / "workspaces" / str(SPACE_ID) / "docs" / "a.md").write_text("第二版内容", encoding="utf-8")

        response = client.post(f"/api/v1/documents/{doc['id']}/reindex")

        assert response.status_code == 200
        hits = client.post(
            f"/api/v1/spaces/{SPACE_ID}/documents/search", json={"query": "第二版"}
        ).json()["hits"]
        assert hits
