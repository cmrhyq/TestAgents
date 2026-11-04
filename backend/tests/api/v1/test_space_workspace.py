"""空间 API 与工作目录的联动：创建、目录树、`AGENTS.md` 读写与删除归档。

仅替换数据库依赖与工作目录根，其余走真实路由与异常处理器。
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.deps import get_db
from src.data.models.base import Base
from src.workspace import manager as workspace_module
from src.workspace.manager import WorkspaceManager


@pytest.fixture()
def app_client(tmp_path) -> Generator[TestClient, None, None]:
    """返回挂载真实 app 的客户端，数据库与工作目录根指向临时目录。

    使用真实 app 以覆盖异常处理器与路由装配；TestClient 不进 with 上下文，
    因此不触发 lifespan，不会连接真实数据库。
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    def _get_db() -> Generator[Session, None, None]:
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # 让 get_workspace_manager() 返回指向临时根的实例
    previous = workspace_module._manager
    workspace_module._manager = WorkspaceManager(root=tmp_path / "workspaces")

    from app import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = _get_db

    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()
        workspace_module._manager = previous
        engine.dispose()


def _create_space(client: TestClient, name: str = "用户中心") -> dict:
    """创建空间并返回响应体。"""
    response = client.post("/api/v1/spaces/", json={"name": name, "description": "测试"})
    assert response.status_code == 201, response.text
    return response.json()


class TestCreateSpaceCreatesWorkspace:
    """创建空间时落盘初始目录与文件。"""

    def test_creates_directory_with_initial_files(self, app_client, tmp_path):
        space = _create_space(app_client)
        space_dir = tmp_path / "workspaces" / str(space["id"])

        assert space_dir.is_dir()
        assert (space_dir / "AGENTS.md").is_file()
        assert (space_dir / "memory" / "MEMORY.md").is_file()
        assert (space_dir / "docs" / "README.md").is_file()
        assert (space_dir / "testcases").is_dir()
        assert (space_dir / "artifacts").is_dir()

    def test_response_carries_workspace_path(self, app_client):
        space = _create_space(app_client)
        normalized = space["workspace_path"].replace("\\", "/")
        assert normalized.endswith(f"workspaces/{space['id']}")

    def test_agents_md_mentions_space_name(self, app_client, tmp_path):
        space = _create_space(app_client, "支付网关")
        content = (tmp_path / "workspaces" / str(space["id"]) / "AGENTS.md").read_text(encoding="utf-8")
        assert "支付网关" in content


class TestTree:
    """目录树查询，含空间不存在时的 404。"""

    def test_tree_returns_initial_structure(self, app_client):
        space = _create_space(app_client)

        response = app_client.get(f"/api/v1/spaces/{space['id']}/tree")

        assert response.status_code == 200, response.text
        names = {node["name"] for node in response.json()["nodes"]}
        assert {"AGENTS.md", "memory", "docs", "testcases", "artifacts"} <= names

    def test_tree_for_missing_space_404(self, app_client):
        assert app_client.get("/api/v1/spaces/999/tree").status_code == 404


class TestAgentsMd:
    """`AGENTS.md` 读写往返。"""

    def test_roundtrip(self, app_client):
        space = _create_space(app_client)
        url = f"/api/v1/spaces/{space['id']}/agents-md"

        assert "AGENTS.md" not in app_client.get(url).json()["content"]

        written = app_client.put(url, json={"content": "# 我的约定\n- 只用测试账号"})
        assert written.status_code == 200

        assert app_client.get(url).json()["content"] == "# 我的约定\n- 只用测试账号"


class TestDeleteSpaceArchivesWorkspace:
    """删除空间时将目录归档，内容保留。"""

    def test_directory_is_archived_not_removed(self, app_client, tmp_path):
        space = _create_space(app_client)
        space_dir = tmp_path / "workspaces" / str(space["id"])
        (space_dir / "artifacts" / "keep.txt").write_text("重要产物", encoding="utf-8")

        assert app_client.delete(f"/api/v1/spaces/{space['id']}").status_code == 204

        assert not space_dir.exists()
        archived = list((tmp_path / "workspaces").glob(".deleted-*"))
        assert len(archived) == 1
        assert (archived[0] / "artifacts" / "keep.txt").read_text(encoding="utf-8") == "重要产物"


class TestDuplicateName:
    """空间重名返回 409。"""

    def test_conflict_returns_409(self, app_client):
        _create_space(app_client, "重复名")
        response = app_client.post("/api/v1/spaces/", json={"name": "重复名"})
        assert response.status_code == 409
