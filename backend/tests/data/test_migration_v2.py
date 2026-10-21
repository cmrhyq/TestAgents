"""v2 迁移测试：旧库 -> Agent 平台 schema。

重点验证三件事：
1. 旧 ``mode`` 取值（Run/Ask/Plan）被正确归一化为 agent/ask/plan
2. ``conversation`` 表重建时**不能**因为外键级联把 message 行吃掉
3. 迁移幂等：连跑两次结果一致
"""

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from src.data.migration.v2_agent_migration import migrate_v2

# 旧 schema 的最小复刻：包含 mode 的旧 CHECK 约束与 message 外键
_OLD_SCHEMA = """
CREATE TABLE space (
    id INTEGER NOT NULL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE environment (
    id INTEGER NOT NULL PRIMARY KEY,
    space_id INTEGER NOT NULL REFERENCES space(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    description TEXT,
    variables TEXT,
    is_default INTEGER NOT NULL DEFAULT 1,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE conversation (
    id INTEGER NOT NULL PRIMARY KEY,
    space_id INTEGER REFERENCES space(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT 'Ask' CHECK (mode IN ('Ask','Plan','Run')),
    status INTEGER NOT NULL DEFAULT 1 CHECK (status IN (0,1)),
    last_message_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE message (
    id INTEGER NOT NULL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversation(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content TEXT NOT NULL DEFAULT '',
    meta TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX idx_conversation_space ON conversation(space_id);
CREATE INDEX idx_message_conv ON message(conversation_id);

INSERT INTO space (id, name, description, status, created_at, updated_at)
VALUES (1, '老空间', '历史数据', 1, '2026-01-01T00:00:00.000', '2026-01-01T00:00:00.000');
INSERT INTO environment (id, space_id, name, base_url, description, variables, is_default, status, created_at, updated_at)
VALUES (10, 1, 'dev', 'http://dev.local', '', '{}', 1, 1, '2026-01-01T00:00:00.000', '2026-01-01T00:00:00.000');
INSERT INTO conversation (id, space_id, title, mode, status, last_message_at, created_at, updated_at)
VALUES (100, 1, 'run 会话', 'Run', 1, NULL, '2026-01-01T00:00:00.000', '2026-01-01T00:00:00.000');
INSERT INTO conversation (id, space_id, title, mode, status, last_message_at, created_at, updated_at)
VALUES (101, 1, 'ask 会话', 'Ask', 1, NULL, '2026-01-01T00:00:00.000', '2026-01-01T00:00:00.000');
INSERT INTO conversation (id, space_id, title, mode, status, last_message_at, created_at, updated_at)
VALUES (102, 1, 'plan 会话', 'Plan', 1, NULL, '2026-01-01T00:00:00.000', '2026-01-01T00:00:00.000');
INSERT INTO message (id, conversation_id, role, content, meta, created_at)
VALUES (1000, 100, 'user', '历史提问', '{}', '2026-01-01T00:00:01.000');
INSERT INTO message (id, conversation_id, role, content, meta, created_at)
VALUES (1001, 100, 'assistant', '历史回答', '{}', '2026-01-01T00:00:02.000');
"""


@pytest.fixture()
def old_db(tmp_path) -> Path:
    """造一个旧 schema 的 SQLite 库。"""
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(_OLD_SCHEMA)
    conn.commit()
    conn.close()
    return db_path


def _engine(db_path: Path):
    return create_engine(f"sqlite:///{db_path}")


class TestMigration:
    def test_adds_workspace_path_and_backfills(self, old_db):
        engine = _engine(old_db)
        migrate_v2(engine)

        with engine.connect() as conn:
            row = conn.execute(text("SELECT workspace_path FROM space WHERE id = 1")).one()
        assert row[0] == "workspaces/1"

    def test_adds_is_production_default_zero(self, old_db):
        engine = _engine(old_db)
        migrate_v2(engine)

        with engine.connect() as conn:
            row = conn.execute(text("SELECT is_production FROM environment WHERE id = 10")).one()
        assert row[0] == 0

    def test_normalizes_mode_values(self, old_db):
        engine = _engine(old_db)
        migrate_v2(engine)

        with engine.connect() as conn:
            rows = dict(conn.execute(text("SELECT id, mode FROM conversation")).all())
        assert rows == {100: "agent", 101: "ask", 102: "plan"}

    def test_preserves_messages_during_rebuild(self, old_db):
        """重建 conversation 时若外键仍开启，DROP TABLE 会级联删掉 message。"""
        engine = _engine(old_db)
        migrate_v2(engine)

        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM message")).scalar()
        assert count == 2

    def test_new_conversation_columns_present(self, old_db):
        engine = _engine(old_db)
        migrate_v2(engine)

        columns = {c["name"] for c in inspect(engine).get_columns("conversation")}
        assert {"skill_names", "environment_id"} <= columns

        with engine.connect() as conn:
            row = conn.execute(text("SELECT skill_names, environment_id FROM conversation WHERE id = 100")).one()
        assert row[0] == "[]"
        assert row[1] is None

    def test_can_insert_agent_mode_after_migration(self, old_db):
        """旧的 CHECK 会让插入 'agent' 直接失败，迁移后必须能写入。"""
        engine = _engine(old_db)
        migrate_v2(engine)

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO conversation (id, space_id, title, mode, skill_names, status, created_at, updated_at) "
                    "VALUES (200, 1, '新会话', 'agent', '[]', 1, '2026-01-02T00:00:00.000', '2026-01-02T00:00:00.000')"
                )
            )

    def test_creates_new_tables(self, old_db):
        engine = _engine(old_db)
        migrate_v2(engine)

        tables = set(inspect(engine).get_table_names())
        assert {"space_memory", "knowledge_document", "knowledge_chunk", "skill"} <= tables

    def test_is_idempotent(self, old_db):
        engine = _engine(old_db)
        migrate_v2(engine)
        migrate_v2(engine)

        with engine.connect() as conn:
            modes = dict(conn.execute(text("SELECT id, mode FROM conversation")).all())
            messages = conn.execute(text("SELECT COUNT(*) FROM message")).scalar()
        assert modes == {100: "agent", 101: "ask", 102: "plan"}
        assert messages == 2

    def test_rebuilds_index_after_table_rebuild(self, old_db):
        engine = _engine(old_db)
        migrate_v2(engine)

        indexes = {i["name"] for i in inspect(engine).get_indexes("conversation")}
        assert "idx_conversation_space" in indexes
