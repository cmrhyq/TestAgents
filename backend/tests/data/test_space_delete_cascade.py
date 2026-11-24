"""空间删除的级联覆盖：空间下的所有子数据都应被清掉，其他空间不受影响。

测试库显式开启 ``PRAGMA foreign_keys``，与生产库一致；这样断言才有意义——
ORM 级联与显式删除都要真正生效，不能靠外键「蒙对」。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

import src.data.models  # noqa: F401  确保所有表注册到 metadata
import src.data.services.space_service as space_service_module
from src.data.models.agent_run import AgentRun
from src.data.models.agent_tool_call import AgentToolCall
from src.data.models.base import Base
from src.data.models.conversation import Conversation
from src.data.models.endpoint import Endpoint
from src.data.models.environment import Environment
from src.data.models.knowledge import KnowledgeChunk, KnowledgeDocument
from src.data.models.llm_log import LLMLog
from src.data.models.message import Message
from src.data.models.skill import Skill
from src.data.models.space import Space
from src.data.models.space_memory import SpaceMemory
from src.data.services.space_service import SpaceService

SPACE_ID = 8100
OTHER_SPACE_ID = 8101


class _NoopWorkspace:
    """挡掉真实目录操作。"""

    def archive(self, space_id):  # noqa: ANN001, ANN201
        return None

    def ensure(self, space_id):  # noqa: ANN001, ANN201
        return None


@pytest.fixture(autouse=True)
def _disable_chroma(monkeypatch):
    """默认关掉向量库，避免单测去连真实 Chroma；需要时由用例自行覆盖。"""
    monkeypatch.setattr(
        space_service_module,
        "get_config",
        lambda: SimpleNamespace(chroma=SimpleNamespace(enabled=False)),
    )


@pytest.fixture()
def factory(tmp_path):
    """临时库 sessionmaker，外键约束与生产一致。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'space.db'}")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):  # noqa: ANN001
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    yield maker
    engine.dispose()


@pytest.fixture()
def seeded(factory) -> dict[str, int]:
    """在目标空间下铺满各类子数据，另建一个空间作为对照。"""
    with factory() as session:
        session.add(Space(id=SPACE_ID, name="待删空间", workspace_path=f"workspaces/{SPACE_ID}"))
        session.add(Space(id=OTHER_SPACE_ID, name="保留空间", workspace_path=f"workspaces/{OTHER_SPACE_ID}"))
        session.flush()

        session.add(Environment(space_id=SPACE_ID, name="dev", base_url="http://x"))
        session.add(Endpoint(space_id=SPACE_ID, operation_id="op1", name="查询", path="/a", method="GET"))

        conversation = Conversation(space_id=SPACE_ID, title="会话")
        session.add(conversation)
        session.flush()
        session.add(Message(conversation_id=conversation.id, role="user", content="问"))

        run = AgentRun(space_id=SPACE_ID, conversation_id=conversation.id, title="执行")
        session.add(run)
        session.flush()
        session.add(AgentToolCall(run_id=run.id, tool_name="send_request"))

        session.add(SpaceMemory(space_id=SPACE_ID, title="记忆", content="内容"))

        document = KnowledgeDocument(space_id=SPACE_ID, filename="a.md", file_path="docs/a.md")
        session.add(document)
        session.flush()
        session.add(KnowledgeChunk(space_id=SPACE_ID, document_id=document.id, content="切片", chroma_id="c1"))

        session.add(Skill(name="space-skill", scope="space", space_id=SPACE_ID))
        session.add(Skill(name="builtin-skill", scope="builtin", space_id=None))
        session.add(LLMLog(model_name="test/model", space_id=SPACE_ID, conversation_id=conversation.id, run_id=run.id))

        # 对照空间的数据
        other_conversation = Conversation(space_id=OTHER_SPACE_ID, title="另一个会话")
        session.add(other_conversation)
        session.flush()
        session.add(Message(conversation_id=other_conversation.id, role="user", content="另一个问题"))
        session.add(SpaceMemory(space_id=OTHER_SPACE_ID, title="另一条记忆", content="内容"))
        session.commit()

        return {
            "conversation_id": conversation.id,
            "run_id": run.id,
            "document_id": document.id,
        }


def _count(session: Session, model, *conditions) -> int:
    """统计满足条件的行数。"""
    stmt = select(func.count()).select_from(model)
    if conditions:
        stmt = stmt.where(*conditions)
    return int(session.scalar(stmt) or 0)


class TestSpaceDeleteCascade:
    """删除空间需清空其全部子数据。"""

    def test_all_child_tables_are_cleared(self, factory, seeded, monkeypatch):
        monkeypatch.setattr(space_service_module, "get_workspace_manager", lambda: _NoopWorkspace())
        with factory() as session:
            SpaceService(session).delete_space(SPACE_ID)
            session.commit()

        with factory() as session:
            assert _count(session, Space, Space.id == SPACE_ID) == 0
            assert _count(session, Environment, Environment.space_id == SPACE_ID) == 0
            assert _count(session, Endpoint, Endpoint.space_id == SPACE_ID) == 0
            assert _count(session, Conversation, Conversation.space_id == SPACE_ID) == 0
            assert _count(session, Message, Message.conversation_id == seeded["conversation_id"]) == 0
            assert _count(session, AgentRun, AgentRun.space_id == SPACE_ID) == 0
            assert _count(session, AgentToolCall, AgentToolCall.run_id == seeded["run_id"]) == 0
            assert _count(session, SpaceMemory, SpaceMemory.space_id == SPACE_ID) == 0
            assert _count(session, KnowledgeDocument, KnowledgeDocument.space_id == SPACE_ID) == 0
            assert _count(session, KnowledgeChunk, KnowledgeChunk.space_id == SPACE_ID) == 0

    def test_space_scoped_skills_are_removed_but_builtin_kept(self, factory, seeded, monkeypatch):
        """``skill`` 不建外键也不在 ORM 关系里，需要显式清理。"""
        monkeypatch.setattr(space_service_module, "get_workspace_manager", lambda: _NoopWorkspace())
        with factory() as session:
            SpaceService(session).delete_space(SPACE_ID)
            session.commit()

        with factory() as session:
            assert _count(session, Skill, Skill.space_id == SPACE_ID) == 0
            assert _count(session, Skill, Skill.scope == "builtin") == 1

    def test_other_space_data_is_untouched(self, factory, seeded, monkeypatch):
        monkeypatch.setattr(space_service_module, "get_workspace_manager", lambda: _NoopWorkspace())
        with factory() as session:
            SpaceService(session).delete_space(SPACE_ID)
            session.commit()

        with factory() as session:
            assert _count(session, Space, Space.id == OTHER_SPACE_ID) == 1
            assert _count(session, Conversation, Conversation.space_id == OTHER_SPACE_ID) == 1
            assert _count(session, SpaceMemory, SpaceMemory.space_id == OTHER_SPACE_ID) == 1
            assert _count(session, Message, Message.content == "另一个问题") == 1

    def test_llm_log_cost_history_is_kept(self, factory, seeded, monkeypatch):
        """``llm_log`` 刻意不建外键，成本历史需在空间删除后保留（见 usage_service）。"""
        monkeypatch.setattr(space_service_module, "get_workspace_manager", lambda: _NoopWorkspace())
        with factory() as session:
            SpaceService(session).delete_space(SPACE_ID)
            session.commit()

        with factory() as session:
            assert _count(session, LLMLog, LLMLog.space_id == SPACE_ID) == 1

    def test_no_orphan_rows_left_behind(self, factory, seeded, monkeypatch):
        """删除后不应存在指向已消失父行的子行。"""
        monkeypatch.setattr(space_service_module, "get_workspace_manager", lambda: _NoopWorkspace())
        with factory() as session:
            SpaceService(session).delete_space(SPACE_ID)
            session.commit()

        with factory() as session:
            conversation_ids = set(session.scalars(select(Conversation.id)).all())
            run_ids = set(session.scalars(select(AgentRun.id)).all())
            document_ids = set(session.scalars(select(KnowledgeDocument.id)).all())

            assert {m.conversation_id for m in session.scalars(select(Message)).all()} <= conversation_ids
            assert {c.run_id for c in session.scalars(select(AgentToolCall)).all()} <= run_ids
            assert {k.document_id for k in session.scalars(select(KnowledgeChunk)).all()} <= document_ids

    def test_missing_space_raises(self, factory):
        from src.core.errors import NotFoundError

        with factory() as session, pytest.raises(NotFoundError):
            SpaceService(session).delete_space(999_999)


class TestVectorCollectionCleanup:
    """知识库向量集合在库之外，删除空间时需单独清理，且失败不得阻断删除。"""

    @staticmethod
    def _patch_config(monkeypatch, *, enabled: bool) -> None:
        """覆盖服务层持有的 ``get_config``（模块级导入，需打在 space_service 上）。"""
        monkeypatch.setattr(
            space_service_module,
            "get_config",
            lambda: SimpleNamespace(chroma=SimpleNamespace(enabled=enabled)),
        )

    @staticmethod
    def _patch_manager(monkeypatch, manager) -> None:  # noqa: ANN001
        monkeypatch.setattr("src.core.chroma.chroma_manager.get_chroma_manager", lambda: manager)

    def test_skips_when_chroma_disabled(self, monkeypatch):
        touched: list[str] = []
        self._patch_config(monkeypatch, enabled=False)
        self._patch_manager(monkeypatch, SimpleNamespace(
            list_collections=lambda: touched.append("list") or [],
            delete_collection=lambda name: touched.append(name),
        ))

        SpaceService._drop_vector_collection(SPACE_ID)

        assert touched == []

    def test_drops_existing_collection(self, monkeypatch):
        deleted: list[str] = []
        self._patch_config(monkeypatch, enabled=True)
        self._patch_manager(monkeypatch, SimpleNamespace(
            list_collections=lambda: [f"space_knowledge_{SPACE_ID}"],
            delete_collection=lambda name: deleted.append(name),
        ))

        SpaceService._drop_vector_collection(SPACE_ID)

        assert deleted == [f"space_knowledge_{SPACE_ID}"]

    def test_missing_collection_is_skipped(self, monkeypatch):
        deleted: list[str] = []
        self._patch_config(monkeypatch, enabled=True)
        self._patch_manager(monkeypatch, SimpleNamespace(
            list_collections=lambda: [],
            delete_collection=lambda name: deleted.append(name),
        ))

        SpaceService._drop_vector_collection(SPACE_ID)

        assert deleted == []

    def test_vector_store_failure_is_swallowed(self, monkeypatch):
        def _boom(_name: str) -> None:
            raise RuntimeError("chroma down")

        self._patch_config(monkeypatch, enabled=True)
        self._patch_manager(monkeypatch, SimpleNamespace(
            list_collections=lambda: [f"space_knowledge_{SPACE_ID}"],
            delete_collection=_boom,
        ))

        # 不应抛异常
        SpaceService._drop_vector_collection(SPACE_ID)
