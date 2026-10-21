"""会话 API 测试（空间下会话列表 / 消息 / 删除 / 新字段）。

这几条接口是「空间会话」需求的落地：用户要能看到某个空间下开过哪些对话、
每轮聊了什么，也能删掉不要的。消息没有独立写入接口（只能由对话产生），
所以插入消息直接走 service。
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.deps import get_db
from src.data.models.base import Base

SPACE_ID = 8090
OTHER_SPACE_ID = 8091


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'conv.db'}")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)

    with maker() as session:
        from src.data.models.space import Space

        session.add(Space(id=SPACE_ID, name="会话空间", workspace_path=f"workspaces/{SPACE_ID}"))
        session.add(Space(id=OTHER_SPACE_ID, name="另一个空间", workspace_path=f"workspaces/{OTHER_SPACE_ID}"))
        session.commit()

    yield maker
    engine.dispose()


@pytest.fixture()
def client(factory) -> Generator[TestClient, None, None]:
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

    from app import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = _get_db
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def append_message(factory):
    """直接走 service 追加消息（消息没有独立写入接口）。"""

    def _append(conversation_id: int, role: str, content: str):
        with factory() as session:
            from src.data.services.conversation_service import ConversationService

            ConversationService(session).append_message(conversation_id, role=role, content=content)
            session.commit()

    return _append


def _create(client: TestClient, **overrides) -> dict:
    payload = {"space_id": SPACE_ID, "title": "", "mode": "agent", **overrides}
    response = client.post("/api/v1/conversations/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


class TestConversationCrud:
    def test_create_returns_new_fields(self, client):
        created = _create(client, mode="plan", skill_names=["api-test-design"])

        assert created["mode"] == "plan"
        assert created["skill_names"] == ["api-test-design"]
        assert created["space_id"] == SPACE_ID

    def test_mode_is_normalized_on_create(self, client):
        """历史值 Run/Ask/Plan 也要落到小写标准值，否则 CHECK 约束会拦。"""
        assert _create(client, mode="Ask")["mode"] == "ask"
        assert _create(client, mode="Plan")["mode"] == "plan"

    def test_update_skill_names(self, client):
        created = _create(client)

        updated = client.put(f"/api/v1/conversations/{created['id']}", json={"skill_names": ["a", "b"]})

        assert updated.status_code == 200
        assert updated.json()["skill_names"] == ["a", "b"]

    def test_update_mode_normalized(self, client):
        created = _create(client)

        updated = client.put(f"/api/v1/conversations/{created['id']}", json={"mode": "RUN"})

        assert updated.json()["mode"] == "agent"

    def test_messages_are_listed_in_order(self, client, append_message):
        cid = _create(client)["id"]
        append_message(cid, "user", "问")
        append_message(cid, "assistant", "答")

        listed = client.get(f"/api/v1/conversations/{cid}/messages")

        assert listed.status_code == 200
        assert [m["content"] for m in listed.json()["items"]] == ["问", "答"]

    def test_detail_includes_messages(self, client, append_message):
        cid = _create(client)["id"]
        append_message(cid, "user", "问")

        detail = client.get(f"/api/v1/conversations/{cid}")

        assert detail.status_code == 200
        assert len(detail.json()["messages"]) == 1

    def test_title_generated_from_first_message(self, client, append_message):
        """新会话标题为空时用首条 user 消息生成，否则列表里全是一串空标题。"""
        cid = _create(client)["id"]
        assert client.get(f"/api/v1/conversations/{cid}").json()["title"] == ""

        append_message(cid, "user", "帮我测一下用户登录接口")

        assert client.get(f"/api/v1/conversations/{cid}").json()["title"] == "帮我测一下用户登录接口"

    def test_long_title_is_truncated(self, client, append_message):
        cid = _create(client)["id"]
        append_message(cid, "user", "长" * 100)

        title = client.get(f"/api/v1/conversations/{cid}").json()["title"]
        assert len(title) <= 31
        assert title.endswith("…")

    def test_delete_removes_conversation(self, client):
        cid = _create(client)["id"]

        assert client.delete(f"/api/v1/conversations/{cid}").status_code == 204
        assert client.get(f"/api/v1/conversations/{cid}").status_code == 404

    def test_delete_cascades_messages(self, client, append_message, factory):
        cid = _create(client)["id"]
        append_message(cid, "user", "问")

        client.delete(f"/api/v1/conversations/{cid}")

        with factory() as session:
            from src.data.models.message import Message

            assert session.query(Message).filter_by(conversation_id=cid).count() == 0

    def test_missing_conversation_is_404(self, client):
        assert client.get("/api/v1/conversations/999999").status_code == 404


class TestSpaceConversationList:
    def test_filters_by_space(self, client):
        _create(client)
        _create(client)
        _create(client, space_id=OTHER_SPACE_ID)

        listed = client.get("/api/v1/conversations/", params={"space_id": SPACE_ID})

        assert listed.status_code == 200
        assert listed.json()["total"] == 2
        assert {item["space_id"] for item in listed.json()["items"]} == {SPACE_ID}

    def test_pagination(self, client):
        for _ in range(3):
            _create(client)

        page = client.get("/api/v1/conversations/", params={"space_id": SPACE_ID, "page": 1, "page_size": 2})

        assert page.json()["total"] == 3
        assert len(page.json()["items"]) == 2
