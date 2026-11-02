"""v3 迁移：test_run -> agent_run，新增 agent_tool_call，删除遗留用例三表。

要解决五件事：

1. **拆旧视图**：``v_run_overview`` / ``v_api_pass_rate`` / ``v_scenario_distribution``
   分别引用 ``test_summary`` / ``test_result`` / ``test_case``。SQLite 的视图是惰性的，
   DROP TABLE 不会报错，但之后每次查询视图都是 ``no such table``。
2. **建新表**：``agent_run`` / ``agent_tool_call``（由 ``create_all`` 完成）。
3. **搬迁老数据**：``test_run`` 的行按语义映射写入 ``agent_run``，**主键原样保留**，
   这样 ``report.run_id`` 一个值都不用改。
4. **重建 report**：SQLite 不能 ALTER 外键，只能建新表 + 拷数据 + 改名。
   ⚠️ 这一步必须在 DROP ``test_run`` **之前**完成：外键开启时
   ``DROP TABLE test_run`` 会隐式 ``DELETE FROM test_run``，把 report 行级联删光。
5. **补 llm_log.run_id**：让 token 成本能按执行轮次聚合。

全部操作幂等：重复执行不会报错，也不会重复改数据。
"""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from src.core.logging import get_logger
from src.data.models.base import Base

logger = get_logger(__name__)

#: 旧视图名。都要先删掉，否则会一直指向已删除的表。
_LEGACY_VIEWS = (
    "v_run_overview",
    "v_api_pass_rate",
    "v_scenario_distribution",
)

#: 旧表按「子表 -> 父表」顺序删除
_LEGACY_TABLES = (
    "test_result",
    "test_summary",
    "test_case",
    "test_run",
)

_LEGACY_TRIGGERS = (
    "trg_test_run_updated",
    "trg_test_case_updated",
)

_REPORT_DDL = """
CREATE TABLE report__v3 (
    id INTEGER NOT NULL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES agent_run(id) ON DELETE CASCADE,
    format TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    generated_at TEXT NOT NULL,
    CONSTRAINT ck_report_format CHECK (format IN ('excel','html','markdown','json'))
)
"""

#: 老列 -> 新列的语义映射（写进 docstring 备查）
#:
#: | 老列                        | 新列              | 说明                                   |
#: |-----------------------------|-------------------|----------------------------------------|
#: | total_cases                 | tool_call_count   | 量级指标，历史数据本就为零写入         |
#: | passed_cases                | ok_count          | 同上                                   |
#: | error_cases + failed_cases  | error_count       | 老表把「失败」「错误」分开，新表合一   |
#: | pass_rate                   | success_rate      | 口径一致（0-100）                      |
#: | total_duration（秒）        | duration_ms       | ×1000                                  |
#: | status='pending'            | 'cancelled'       | 新表没有 pending，老 pending 必然是废弃 |
#: | name                        | title             | —                                      |
#: | （无）                      | conversation_id   | 老表无此列，置 NULL                    |
_LEGACY_RUN_COPY = """
INSERT OR IGNORE INTO agent_run (
    id, space_id, environment_id, conversation_id, title, mode, trigger_type,
    llm_provider, llm_model, status, started_at, finished_at, duration_ms,
    tool_call_count, ok_count, error_count, success_rate, avg_response_time,
    llm_call_count, total_tokens, cost_usd, error_message, created_at, updated_at
)
SELECT
    id,
    space_id,
    environment_id,
    NULL,
    COALESCE(NULLIF(name, ''), '历史执行记录'),
    'agent',
    CASE
        WHEN trigger_type IN ('chat', 'manual', 'scheduled', 'ci') THEN trigger_type
        ELSE 'manual'
    END,
    COALESCE(llm_provider, ''),
    COALESCE(llm_model, ''),
    CASE status
        WHEN 'pending' THEN 'cancelled'
        WHEN 'running' THEN 'cancelled'
        WHEN 'completed' THEN 'completed'
        WHEN 'failed' THEN 'failed'
        WHEN 'cancelled' THEN 'cancelled'
        ELSE 'cancelled'
    END,
    started_at,
    finished_at,
    CAST(COALESCE(total_duration, 0) * 1000 AS INTEGER),
    COALESCE(total_cases, 0),
    COALESCE(passed_cases, 0),
    COALESCE(error_cases, 0) + COALESCE(failed_cases, 0),
    COALESCE(pass_rate, 0.0),
    0.0,
    0,
    0,
    0.0,
    COALESCE(error_message, ''),
    created_at,
    updated_at
FROM test_run
"""


def migrate_v3(engine: Engine) -> None:
    """执行 v3 迁移（幂等）。"""
    if engine.dialect.name != "sqlite":
        logger.warning("v3 迁移仅实现 SQLite 路径，跳过", dialect=engine.dialect.name)
        return

    tables = set(inspect(engine).get_table_names())

    # ① 视图先拆：它们指向即将消失的表
    _drop_legacy_views(engine)

    # ② 建新表（create_all 只建缺失的表，不动已有表）
    Base.metadata.create_all(engine)

    # ③ 老库才需要搬迁 + 重建 report + 删老表
    if "test_run" in tables:
        _copy_legacy_runs(engine)
        # ⚠️ 必须在 DROP test_run 之前，否则 report 行被级联删光
        _rebuild_report(engine)
        _drop_legacy_tables(engine)
    else:
        logger.debug("未发现 test_run，跳过遗留数据搬迁")

    # ④ llm_log 补 run_id（与数据搬迁解耦，单独幂等）
    _add_llm_log_run_id(engine)

    logger.info("v3 迁移完成")


# ---------------------------------------------------------------------------
# 步骤
# ---------------------------------------------------------------------------


def _drop_legacy_views(engine: Engine) -> None:
    with engine.begin() as conn:
        for view in _LEGACY_VIEWS:
            conn.execute(text(f"DROP VIEW IF EXISTS {view}"))


def _copy_legacy_runs(engine: Engine) -> None:
    """把 test_run 的历史行搬进 agent_run（主键保留）。"""
    columns = {c["name"] for c in inspect(engine).get_columns("test_run")}
    if not columns:
        return
    with engine.begin() as conn:
        before = conn.execute(text("SELECT COUNT(*) FROM test_run")).scalar() or 0
        if not before:
            logger.debug("test_run 无数据，跳过搬迁")
            return
        conn.execute(text(_LEGACY_RUN_COPY))
        moved = conn.execute(text("SELECT COUNT(*) FROM agent_run")).scalar() or 0
    logger.info("遗留执行批次已搬迁", legacy_rows=before, agent_run_rows=moved)


def _rebuild_report(engine: Engine) -> None:
    """把 report 的外键从 test_run 改指 agent_run。

    走 raw connection 手关外键：SQLAlchemy 的 connect 事件会在每次连接时
    把 ``foreign_keys`` 打开，``engine.connect()`` 关不掉。
    """
    ddl = _table_sql(engine, "report")
    if not ddl:
        return  # 表不存在，create_all 会按新结构建
    if "test_run" not in ddl:
        return  # 已经是新结构

    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("DROP TABLE IF EXISTS report__v3")
        cursor.execute(_REPORT_DDL)
        # 只搬仍有关联执行记录的 report 行，孤儿行直接丢弃（否则 FK 会拒绝）
        cursor.execute(
            "INSERT INTO report__v3 (id, run_id, format, file_path, file_size, generated_at) "
            "SELECT id, run_id, format, file_path, COALESCE(file_size, 0), generated_at "
            "FROM report WHERE run_id IN (SELECT id FROM agent_run)"
        )
        kept = cursor.execute("SELECT COUNT(*) FROM report__v3").fetchone()[0]
        total = cursor.execute("SELECT COUNT(*) FROM report").fetchone()[0]
        cursor.execute("DROP TABLE report")
        cursor.execute("ALTER TABLE report__v3 RENAME TO report")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_report_run ON report(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_report_format ON report(format)")
        cursor.execute("PRAGMA foreign_keys=ON")
        raw.commit()
        if total != kept:
            logger.warning("重建 report 时丢弃了孤儿行", dropped=total - kept)
        logger.info("report 表已重建（外键改指 agent_run）", rows=kept)
    except Exception:
        raw.rollback()
        logger.error("report 表重建失败，已回滚")
        raise
    finally:
        raw.close()


def _drop_legacy_tables(engine: Engine) -> None:
    """删除遗留用例表与触发器（子表先删）。"""
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        for table in _LEGACY_TABLES:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        for trigger in _LEGACY_TRIGGERS:
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger}")
        cursor.execute("PRAGMA foreign_keys=ON")
        raw.commit()
        logger.info("遗留用例表已删除", tables=list(_LEGACY_TABLES))
    except Exception:
        raw.rollback()
        logger.error("删除遗留表失败，已回滚")
        raise
    finally:
        raw.close()


def _add_llm_log_run_id(engine: Engine) -> None:
    """给 llm_log 补 run_id 列与索引。

    **刻意不建外键**：``llm_log`` 是统计表，要能挺过执行记录清理。
    加 FK 会在清理 90 天前的 run 时把成本历史一起带走。
    """
    inspector = inspect(engine)
    if "llm_log" not in set(inspector.get_table_names()):
        return
    existing = {c["name"] for c in inspector.get_columns("llm_log")}
    if "run_id" not in existing:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE llm_log ADD COLUMN run_id INTEGER DEFAULT NULL"))
        logger.info("已补列", table="llm_log", column="run_id")

    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_llm_log_run ON llm_log (run_id, created_at)"))


def _table_sql(engine: Engine, table: str) -> str:
    with engine.connect() as conn:
        ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :name"),
            {"name": table},
        ).scalar()
    return ddl or ""
