"""LongTermMemory 单元测试。

覆盖：增删改查、软删过滤、空间隔离、关键词召回、MEMORY.md 镜像同步。
使用临时 SQLite，不依赖全局数据库单例。
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.data.models.base import Base
from src.memory.longterm import LongTermMemory
from src.workspace.manager import WorkspaceManager

SPACE_A = 1001
SPACE_B = 1002


@pytest.fixture()
def session_scope(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mem.db'}")
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


@pytest.fixture()
def memory(tmp_path, session_scope) -> LongTermMemory:
    return LongTermMemory(
        workspace=WorkspaceManager(root=tmp_path / "workspaces"),
        session_scope=session_scope,
    )


class TestAdd:
    def test_add_returns_entity(self, memory):
        entry = memory.add(SPACE_A, "登录用 v2", "v1 已废弃，token 2h 过期", category="decision", tags=["auth"])

        assert entry.id
        assert entry.space_id == SPACE_A
        assert entry.status == 1

    def test_invalid_category_rejected(self, memory):
        with pytest.raises(ValueError, match="category"):
            memory.add(SPACE_A, "t", "c", category="unknown")

    def test_default_category_is_fact(self, memory):
        assert memory.add(SPACE_A, "t", "c").category == "fact"


class TestList:
    def test_lists_only_own_space(self, memory):
        memory.add(SPACE_A, "A 的记忆", "内容")
        memory.add(SPACE_B, "B 的记忆", "内容")

        titles = [m.title for m in memory.list(SPACE_A)]

        assert titles == ["A 的记忆"]

    def test_filter_by_category(self, memory):
        memory.add(SPACE_A, "决策", "c", category="decision")
        memory.add(SPACE_A, "事实", "c", category="fact")

        result = memory.list(SPACE_A, category="decision")

        assert [m.title for m in result] == ["决策"]

    def test_keyword_matches_content(self, memory):
        memory.add(SPACE_A, "无关标题", "这里提到了 token 刷新")
        memory.add(SPACE_A, "另一条", "完全无关")

        assert [m.title for m in memory.list(SPACE_A, keyword="token")] == ["无关标题"]

    def test_newest_first(self, memory):
        first = memory.add(SPACE_A, "先写", "c")
        second = memory.add(SPACE_A, "后写", "c")

        ids = [m.id for m in memory.list(SPACE_A)]

        # 时间戳精度可能相同，用插入顺序兜底：后写的应排在前面
        assert ids.index(second.id) <= ids.index(first.id)

    def test_soft_deleted_excluded(self, memory):
        entry = memory.add(SPACE_A, "待删", "c")
        memory.delete(entry.id, hard=False)

        assert memory.list(SPACE_A) == []


class TestRecall:
    def test_matches_title(self, memory):
        memory.add(SPACE_A, "鉴权方式", "Bearer token")
        memory.add(SPACE_A, "分页约定", "page/page_size")

        assert [m.title for m in memory.recall(SPACE_A, "鉴权")] == ["鉴权方式"]

    def test_matches_tags(self, memory):
        memory.add(SPACE_A, "某条", "内容", tags=["auth", "token"])

        assert [m.title for m in memory.recall(SPACE_A, "aut")]

    def test_empty_query_returns_recent(self, memory):
        memory.add(SPACE_A, "一", "c")
        memory.add(SPACE_A, "二", "c")

        assert len(memory.recall(SPACE_A, "")) == 2

    def test_no_match_returns_empty(self, memory):
        memory.add(SPACE_A, "一", "c")
        assert memory.recall(SPACE_A, "完全不存在的词") == []

    def test_respects_limit(self, memory):
        for i in range(5):
            memory.add(SPACE_A, f"条目{i}", "共同关键词 kw")
        assert len(memory.recall(SPACE_A, "kw", limit=2)) == 2


class TestUpdate:
    def test_updates_fields(self, memory):
        entry = memory.add(SPACE_A, "旧标题", "旧内容")

        updated = memory.update(entry.id, title="新标题", content="新内容")

        assert updated.title == "新标题"
        assert updated.content == "新内容"

    def test_updates_timestamp(self, memory):
        entry = memory.add(SPACE_A, "t", "c")
        before = entry.updated_at

        updated = memory.update(entry.id, content="changed")

        assert updated.updated_at >= before

    def test_unknown_id_raises(self, memory):
        with pytest.raises(LookupError):
            memory.update(999999, content="x")


class TestDelete:
    def test_soft_delete_keeps_row(self, memory, session_scope):
        entry = memory.add(SPACE_A, "t", "c")

        memory.delete(entry.id, hard=False)

        with session_scope() as session:
            row = session.get(type(entry), entry.id)
            assert row is not None
            assert row.status == 0

    def test_hard_delete_removes_row(self, memory, session_scope):
        entry = memory.add(SPACE_A, "t", "c")

        memory.delete(entry.id, hard=True)

        with session_scope() as session:
            assert session.get(type(entry), entry.id) is None

    def test_delete_unknown_is_noop(self, memory):
        memory.delete(999999)


class TestMarkdownSync:
    def test_creates_mirror_file(self, memory, tmp_path):
        entry = memory.add(SPACE_A, "登录用 v2", "v1 已废弃", category="decision", tags=["auth"])
        path = memory.sync_markdown(SPACE_A)

        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert "登录用 v2" in content
        assert "v1 已废弃" in content
        assert "#auth" in content
        assert entry.title in content

    def test_groups_by_category(self, memory):
        memory.add(SPACE_A, "一条决策", "c", category="decision")
        memory.add(SPACE_A, "一条事实", "c", category="fact")

        content = memory.sync_markdown(SPACE_A).read_text(encoding="utf-8")

        assert "## decision" in content
        assert "## fact" in content

    def test_empty_space_shows_placeholder(self, memory):
        content = memory.sync_markdown(SPACE_A).read_text(encoding="utf-8")
        assert "尚无记忆条目" in content

    def test_deleted_entry_removed_from_mirror(self, memory):
        entry = memory.add(SPACE_A, "会被删掉的", "c")
        memory.sync_markdown(SPACE_A)

        memory.delete(entry.id)
        content = memory.sync_markdown(SPACE_A).read_text(encoding="utf-8")

        assert "会被删掉的" not in content

    def test_mirror_path_is_space_memory_dir(self, memory, tmp_path):
        path = memory.sync_markdown(SPACE_A)
        assert path == (tmp_path / "workspaces" / str(SPACE_A) / "memory" / "MEMORY.md").resolve()
