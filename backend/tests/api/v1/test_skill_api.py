"""Skills API：列表、详情、zip 导入与启停。

服务实例与工作区指向临时目录，其余走真实路由与表结构。
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.deps import get_db
from src.data.models.base import Base
from src.skill import service as skill_service_module
from src.skill.service import SkillService
from src.workspace import manager as workspace_module
from src.workspace.manager import WorkspaceManager

SPACE_ID = 4242


def _skill_md(name: str, description: str = "desc", body: str = "正文") -> str:
    """生成最小可解析的 `SKILL.md` 文本。"""
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"


def _write_skill(root: Path, name: str, description: str = "desc") -> None:
    """在 `root` 下写入一个技能目录。"""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(_skill_md(name, description), encoding="utf-8")


def _zip(entries: dict[str, str]) -> bytes:
    """把 `{路径: 内容}` 打成 zip 字节。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buffer.getvalue()


@pytest.fixture()
def client(tmp_path) -> Generator[TestClient, None, None]:
    """返回挂载真实 app 的客户端，并替换全局工作区与服务单例。"""
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

    builtin = tmp_path / "skills"
    builtin.mkdir()
    _write_skill(builtin, "builtin-alpha", description="内置")

    ws = WorkspaceManager(root=tmp_path / "workspaces")
    ws.create(SPACE_ID, "测试空间")

    prev_manager = workspace_module._manager
    prev_service = skill_service_module._service
    workspace_module._manager = ws
    skill_service_module._service = SkillService(builtin_root=builtin, workspace=ws)

    from app import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = _get_db
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()
        workspace_module._manager = prev_manager
        skill_service_module._service = prev_service
        engine.dispose()


class TestList:
    """技能列表与默认启用状态。"""

    def test_lists_builtin_skill(self, client):
        response = client.get("/api/v1/skills")

        assert response.status_code == 200, response.text
        names = [item["name"] for item in response.json()["items"]]
        assert "builtin-alpha" in names

    def test_every_skill_enabled_by_default(self, client):
        items = client.get("/api/v1/skills").json()["items"]
        assert all(item["enabled"] for item in items)


class TestImport:
    """zip 导入的落盘结果与非法包拒绝。"""

    def test_imports_into_space(self, client, tmp_path):
        response = client.post(
            "/api/v1/skills/import",
            params={"space_id": SPACE_ID},
            files={"file": ("pkg.zip", _zip({"mine/SKILL.md": _skill_md("mine")}), "application/zip")},
        )

        assert response.status_code == 200, response.text
        names = [item["name"] for item in response.json()["items"]]
        assert "mine" in names
        assert (tmp_path / "workspaces" / str(SPACE_ID) / ".skills" / "mine" / "SKILL.md").is_file()

    def test_rejects_zip_without_skill_md(self, client):
        response = client.post(
            "/api/v1/skills/import",
            params={"space_id": SPACE_ID},
            files={"file": ("bad.zip", _zip({"x.txt": "hi"}), "application/zip")},
        )

        assert response.status_code == 422

    def test_rejects_zip_slip(self, client, tmp_path):
        response = client.post(
            "/api/v1/skills/import",
            params={"space_id": SPACE_ID},
            files={"file": ("evil.zip", _zip({"../evil/SKILL.md": _skill_md("evil")}), "application/zip")},
        )

        assert response.status_code == 422
        assert not (tmp_path / "workspaces" / "evil").exists()


class TestToggle:
    """启停开关的即时生效与跨请求持久化。"""

    def test_disable_then_listed_as_disabled(self, client):
        url = "/api/v1/skills/builtin-alpha"

        patched = client.patch(url, params={"space_id": SPACE_ID}, json={"enabled": False})
        assert patched.status_code == 200, patched.text
        assert patched.json()["enabled"] is False

        items = client.get("/api/v1/skills", params={"space_id": SPACE_ID}).json()["items"]
        target = next(item for item in items if item["name"] == "builtin-alpha")
        assert target["enabled"] is False

    def test_toggle_persists_across_requests(self, client):
        client.patch("/api/v1/skills/builtin-alpha", params={"space_id": SPACE_ID}, json={"enabled": False})

        detail = client.get("/api/v1/skills/builtin-alpha", params={"space_id": SPACE_ID})
        assert detail.json()["enabled"] is False

    def test_unknown_skill_404(self, client):
        response = client.patch("/api/v1/skills/ghost", json={"enabled": False})
        assert response.status_code == 404


class TestDetail:
    """详情接口返回正文与作用域。"""

    def test_returns_body(self, client):
        response = client.get("/api/v1/skills/builtin-alpha")

        assert response.status_code == 200
        assert "正文" in response.json()["body"]
        assert response.json()["scope"] == "builtin"
