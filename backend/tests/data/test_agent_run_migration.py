"""v3 迁移测试：test_* 执行链路 -> agent_run / agent_tool_call。

重点验证四件事：

1. ``test_run`` 的行按语义映射进 ``agent_run``，且**主键保留**
2. ``report`` 的外键改指 ``agent_run``，且**行不能在 DROP test_run 时被级联删光**
3. 遗留三张用例表 + 旧视图彻底消失
4. 迁移幂等：连跑两次结果一致
"""

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from src.data.migration.v3_agent_run_migration import migrate_v3

# 旧 schema 的最小复刻：test_run 及其三张子表、report 的旧外键、旧视图
_OLD_SCHEMA = """
CREATE TABLE space (
    id INTEGER NOT NULL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    status INTEGER NOT NULL DEFAULT 1,
    workspace_path TEXT NOT NULL DEFAULT '',
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
    is_production INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE test_run (
    id INTEGER NOT NULL PRIMARY KEY,
    space_id INTEGER NOT NULL REFERENCES space(id) ON DELETE CASCADE,
    environment_id INTEGER REFERENCES environment(id) ON DELETE SET NULL,
    name TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    trigger_type TEXT NOT NULL DEFAULT 'manual',
    input_file TEXT,
    input_snapshot TEXT,
    config_snapshot TEXT,
    llm_provider TEXT,
    llm_model TEXT,
    total_cases INTEGER NOT NULL DEFAULT 0,
    passed_cases INTEGER NOT NULL DEFAULT 0,
    failed_cases INTEGER NOT NULL DEFAULT 0,
    skipped_cases INTEGER NOT NULL DEFAULT 0,
    error_cases INTEGER NOT NULL DEFAULT 0,
    pass_rate REAL NOT NULL DEFAULT 0.0,
    started_at TEXT,
    finished_at TEXT,
    total_duration REAL NOT NULL DEFAULT 0.0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE test_case (
    id INTEGER NOT NULL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES test_run(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL
);
CREATE TABLE test_result (
    id INTEGER NOT NULL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES test_run(id) ON DELETE CASCADE,
    test_case_id INTEGER NOT NULL REFERENCES test_case(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending'
);
CREATE TABLE test_summary (
    id INTEGER NOT NULL PRIMARY KEY,
    run_id INTEGER NOT NULL UNIQUE REFERENCES test_run(id) ON DELETE CASCADE
);
CREATE TABLE report (
    id INTEGER NOT NULL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES test_run(id) ON DELETE CASCADE,
    format TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    generated_at TEXT NOT NULL
);
CREATE TABLE llm_log (
    id INTEGER NOT NULL PRIMARY KEY,
    model_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE VIEW v_run_overview AS SELECT id AS run_id FROM test_run;
CREATE VIEW v_api_pass_rate AS SELECT status FROM test_result;
CREATE VIEW v_scenario_distribution AS SELECT case_id FROM test_case;

INSERT INTO space (id, name, description, status, created_at, updated_at)
VALUES (1, '老空间', '', 1, '2026-01-01T00:00:00.000', '2026-01-01T00:00:00.000');
INSERT INTO environment (id, space_id, name, base_url, created_at, updated_at)
VALUES (10, 1, 'dev', 'http://dev.local', '2026-01-01T00:00:00.000', '2026-01-01T00:00:00.000');

-- 一条带统计的历史批次，一条 pending（应被归一化为 cancelled）
INSERT INTO test_run (id, space_id, environment_id, name, status, trigger_type,
                      llm_provider, llm_model, total_cases, passed_cases, failed_cases,
                      error_cases, pass_rate, total_duration, created_at, updated_at)
VALUES (5001, 1, 10, '历史批次', 'completed', 'manual', 'zai', 'glm-4',
        12, 9, 2, 1, 75.0, 1.5, '2026-01-01T00:00:00.000', '2026-01-01T00:00:00.000');
INSERT INTO test_run (id, space_id, name, status, trigger_type, created_at, updated_at)
VALUES (5002, 1, '', 'pending', 'ci', '2026-01-02T00:00:00.000', '2026-01-02T00:00:00.000');

INSERT INTO test_case (id, run_id, case_id) VALUES (9001, 5001, 'c-1');
INSERT INTO test_result (id, run_id, test_case_id, status) VALUES (8001, 5001, 9001, 'passed');
INSERT INTO test_summary (id, run_id) VALUES (7001, 5001);
INSERT INTO report (id, run_id, format, file_path, file_size, generated_at)
VALUES (6001, 5001, 'html', 'reports/r1.html', 1024, '2026-01-01T00:00:00.000');
INSERT INTO llm_log (id, model_name, created_at) VALUES (1, 'glm-4', '2026-01-01T00:00:00.000');
"""


@pytest.fixture()
def old_db(tmp_path) -> Path:
    db_path = tmp_path / "old_v3.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(_OLD_SCHEMA)
    conn.commit()
    conn.close()
    return db_path


def _engine(db_path: Path):
    return create_engine(f"sqlite:///{db_path}")


def _tables(engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def _views(engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='view'")).fetchall()
    return {row[0] for row in rows}


@pytest.mark.unit
class TestMigrationV3:
    def test_legacy_tables_are_dropped(self, old_db):
        engine = _engine(old_db)
        migrate_v3(engine)

        tables = _tables(engine)
        for legacy in ("test_run", "test_case", "test_result", "test_summary"):
            assert legacy not in tables
        assert "agent_run" in tables
        assert "agent_tool_call" in tables

    def test_legacy_views_are_dropped(self, old_db):
        engine = _engine(old_db)
        migrate_v3(engine)

        views = _views(engine)
        assert views == set(), views

    def test_runs_are_copied_with_semantic_mapping(self, old_db):
        engine = _engine(old_db)
        migrate_v3(engine)

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, title, mode, status, tool_call_count, ok_count, "
                    "error_count, success_rate, duration_ms, conversation_id FROM agent_run WHERE id = 5001"
                )
            ).one()

        # 主键原样保留 —— 这是 report.run_id 不用改值的前提
        assert row[0] == 5001
        assert row[1] == "历史批次"  # name -> title
        assert row[2] == "agent"
        assert row[3] == "completed"
        assert row[4] == 12  # total_cases -> tool_call_count
        assert row[5] == 9  # passed_cases -> ok_count
        assert row[6] == 3  # error_cases + failed_cases
        assert row[7] == 75.0  # pass_rate -> success_rate
        assert row[8] == 1500  # 1.5 秒 -> 1500 毫秒
        assert row[9] is None  # 老表无 conversation_id

    def test_pending_status_becomes_cancelled(self, old_db):
        engine = _engine(old_db)
        migrate_v3(engine)

        with engine.connect() as conn:
            status = conn.execute(text("SELECT status FROM agent_run WHERE id = 5002")).scalar()
        assert status == "cancelled"

    def test_report_kept_and_fk_points_to_agent_run(self, old_db):
        engine = _engine(old_db)
        migrate_v3(engine)

        ddl = None
        with engine.connect() as conn:
            ddl = conn.execute(text("SELECT sql FROM sqlite_master WHERE name = 'report'")).scalar()
            count = conn.execute(text("SELECT COUNT(*) FROM report")).scalar()

        assert "agent_run" in ddl
        assert "test_run" not in ddl
        # 关键断言：DROP test_run 不能把 report 行级联删光
        assert count == 1

    def test_llm_log_gets_run_id_column(self, old_db):
        engine = _engine(old_db)
        migrate_v3(engine)

        columns = {c["name"] for c in inspect(engine).get_columns("llm_log")}
        assert "run_id" in columns

    def test_data_survives_and_is_idempotent(self, old_db):
        engine = _engine(old_db)
        migrate_v3(engine)
        migrate_v3(engine)  # 再跑一遍

        with engine.connect() as conn:
            runs = conn.execute(text("SELECT COUNT(*) FROM agent_run")).scalar()
        assert runs == 2
