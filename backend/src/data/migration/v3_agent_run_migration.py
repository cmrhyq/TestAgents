"""v3 迁移：``test_run`` 转 ``agent_run``，新增 ``agent_tool_call``，删除遗留用例三表。

SQLite 视图惰性解析，旧视图须先 DROP；不能 ALTER 外键，``report`` 只能重建表改指向，
且须在 DROP ``test_run`` 之前完成，否则外键级联会删光 report 行。各步骤幂等。
"""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from src.core.logging import get_logger
from src.data.models.base import Base

logger = get_logger(__name__)

#: 旧视图名，须先删除，否则会一直指向已删除的表
_LEGACY_VIEWS = (
    "v_run_overview",
    "v_api_pass_rate",
    "v_scenario_distribution",
)

#: 旧表删除顺序：子表先于父表
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

#: 老列到新列的映射要点：用例计数写入 ``tool_call_count`` / ``ok_count``，
#: ``error_cases + failed_cases`` 合并为 ``error_count``，``total_duration`` 秒转毫秒
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
    """执行 v3 迁移，幂等，可重复调用。

    仅实现 SQLite 路径，其他方言只记录告警后返回。

    副作用：删视图、建表、搬数据、重建 ``report`` 并删除遗留表，各步骤自行提交事务。

    Args:
        engine: 目标数据库引擎
    """
    if engine.dialect.name != "sqlite":
        logger.warning("v3 迁移仅实现 SQLite 路径，跳过", dialect=engine.dialect.name)
        return

    tables = set(inspect(engine).get_table_names())

    # 旧视图必须先删，它们引用的表即将被删除
    _drop_legacy_views(engine)

    # create_all 只建缺失的表，不改动已有表
    Base.metadata.create_all(engine)

    # 只有老库才需要搬迁数据、重建 report、删旧表
    if "test_run" in tables:
        _copy_legacy_runs(engine)
        # 必须在 DROP test_run 之前完成，否则 report 行被外键级联删除
        _rebuild_report(engine)
        _drop_legacy_tables(engine)
    else:
        logger.debug("未发现 test_run，跳过遗留数据搬迁")

    # 与数据搬迁解耦，单独幂等
    _add_llm_log_run_id(engine)

    logger.info("v3 迁移完成")


# 步骤


def _drop_legacy_views(engine: Engine) -> None:
    """删除遗留视图。

    SQLite 视图惰性解析，删除其依赖表不会报错，但后续查询视图才会失败，因此先删视图。

    副作用：写库并提交。

    Args:
        engine: 目标数据库引擎
    """
    with engine.begin() as conn:
        for view in _LEGACY_VIEWS:
            conn.execute(text(f"DROP VIEW IF EXISTS {view}"))


def _copy_legacy_runs(engine: Engine) -> None:
    """把 ``test_run`` 的历史行搬进 ``agent_run``，主键原样保留。

    保留主键可使 ``report.run_id`` 无需改写。

    副作用：写库并提交；``test_run`` 无数据时直接返回。

    Args:
        engine: 目标数据库引擎
    """
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
    """重建 ``report`` 表，把外键从 ``test_run`` 改为指向 ``agent_run``。

    SQLite 不能 ALTER 外键，只能建新表搬数据；须用 raw connection 关闭外键，
    因为 SQLAlchemy 的连接事件在每次连接时重新打开 ``foreign_keys``。

    副作用：建临时表、搬数据、删旧表、改名并提交；失败时回滚。

    Args:
        engine: 目标数据库引擎

    Raises:
        Exception: 重建过程中的任何失败，回滚后原样抛出
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
    """删除遗留用例表与触发器，子表先删。

    关闭外键后执行，避免 ``DROP TABLE`` 触发级联删除。

    副作用：写库并提交；失败时回滚。

    Args:
        engine: 目标数据库引擎

    Raises:
        Exception: 删除过程中的任何失败，回滚后原样抛出
    """
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
    """为 ``llm_log`` 增加 ``run_id`` 列与索引。

    不建外键：``llm_log`` 是统计表，需在执行记录清理后仍保留成本历史。

    副作用：写库并提交。

    Args:
        engine: 目标数据库引擎
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
    """读取 ``sqlite_master`` 中指定表的建表语句。

    Args:
        engine: 目标数据库引擎
        table: 表名

    Returns:
        建表 SQL；表不存在时返回空串
    """
    with engine.connect() as conn:
        ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :name"),
            {"name": table},
        ).scalar()
    return ddl or ""
