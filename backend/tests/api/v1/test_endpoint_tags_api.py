"""接口标签的 HTTP 契约。

关注三件事：入参出参都是数组（库里才是 JSON 字符串）、标签筛选参数可用、
``/endpoints/tags`` 不被 ``/endpoints/{id}`` 路由吞掉。
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.deps import get_db
from src.data.models.base import Base
from src.data.models.space import Space

SPACE_ID = 9101


@pytest.fixture()
def session_factory(tmp_path):
    """构造临时库并预置空间。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'tags_api.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        s.add(Space(id=SPACE_ID, name="标签空间", workspace_path=f"workspaces/{SPACE_ID}"))
        s.commit()
    yield factory
    engine.dispose()


@pytest.fixture()
def client(session_factory) -> Generator[TestClient, None, None]:
    """把数据库依赖指向临时库的客户端。"""
    from app import app

    def _get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _payload(path: str, tags: list[str], method: str = "GET") -> dict:
    """构造创建接口的请求体。"""
    return {
        "space_id": SPACE_ID,
        "operation_id": path.strip("/").replace("/", "_") or "root",
        "name": path,
        "path": path,
        "method": method,
        "tags": tags,
    }


class TestCreateAndRead:
    """入参与出参的形态。"""

    def test_create_returns_array(self, client):
        """创建后响应里的 tags 是数组，不是 JSON 字符串。"""
        resp = client.post("/api/v1/endpoints/", json=_payload("/users", ["用户", "鉴权"]))
        assert resp.status_code == 201, resp.text
        assert resp.json()["tags"] == ["用户", "鉴权"]

    def test_list_returns_array(self, client):
        """列表接口同样返回数组，前端无需自行 JSON.parse。"""
        client.post("/api/v1/endpoints/", json=_payload("/users", ["用户"]))

        resp = client.get("/api/v1/endpoints/", params={"space_id": SPACE_ID})
        assert resp.status_code == 200
        assert resp.json()["items"][0]["tags"] == ["用户"]

    def test_update_replaces_tags(self, client):
        """更新时提交数组即整体替换。"""
        created = client.post("/api/v1/endpoints/", json=_payload("/users", ["旧"])).json()

        resp = client.put(f"/api/v1/endpoints/{created['id']}", json={"tags": ["新", "标签"]})
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["新", "标签"]

    def test_reject_too_many_tags(self, client):
        """超过上限返回 422，并在报错里说清上限。"""
        resp = client.post("/api/v1/endpoints/", json=_payload("/many", [f"t{i}" for i in range(11)]))
        assert resp.status_code == 422
        assert "最多" in resp.text

    def test_reject_quote_in_tag(self, client):
        """带双引号的标签破坏精确匹配语义，直接拒绝。"""
        resp = client.post("/api/v1/endpoints/", json=_payload("/quote", ['say "hi"']))
        assert resp.status_code == 422


class TestFilterAndFacets:
    """查询侧：标签筛选与聚合。"""

    def test_filter_by_tag(self, client):
        """``tags=用户`` 只返回带该标签的接口，不命中的不出现。"""
        client.post("/api/v1/endpoints/", json=_payload("/a", ["用户"]))
        client.post("/api/v1/endpoints/", json=_payload("/b", ["用户管理"]))

        resp = client.get("/api/v1/endpoints/", params={"space_id": SPACE_ID, "tags": "用户"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["path"] == "/a"

    def test_filter_multiple_tags_all_mode(self, client):
        """逗号分隔多标签，``tags_mode=all`` 要求同时命中。"""
        client.post("/api/v1/endpoints/", json=_payload("/both", ["用户", "鉴权"]))
        client.post("/api/v1/endpoints/", json=_payload("/only", ["用户"]))

        resp = client.get(
            "/api/v1/endpoints/",
            params={"space_id": SPACE_ID, "tags": "用户,鉴权", "tags_mode": "all"},
        )
        assert resp.json()["total"] == 1

        resp = client.get(
            "/api/v1/endpoints/",
            params={"space_id": SPACE_ID, "tags": "用户,鉴权", "tags_mode": "any"},
        )
        assert resp.json()["total"] == 2

    def test_invalid_tags_mode_rejected(self, client):
        """``tags_mode`` 只接受 any / all。"""
        resp = client.get("/api/v1/endpoints/", params={"space_id": SPACE_ID, "tags_mode": "some"})
        assert resp.status_code == 422

    def test_tag_facets_endpoint(self, client):
        """``/endpoints/tags`` 返回聚合结果，且不会被 ``/{endpoint_id}`` 抢先匹配。"""
        client.post("/api/v1/endpoints/", json=_payload("/a", ["用户", "鉴权"]))
        client.post("/api/v1/endpoints/", json=_payload("/b", ["用户"]))

        resp = client.get("/api/v1/endpoints/tags", params={"space_id": SPACE_ID})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body[0] == {"name": "用户", "count": 2}
        assert {"name": "鉴权", "count": 1} in body

    def test_tag_facets_requires_space(self, client):
        """缺少 space_id 时按必填参数处理，返回 422。"""
        assert client.get("/api/v1/endpoints/tags").status_code == 422
