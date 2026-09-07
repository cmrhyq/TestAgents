"""
数据库初始化与迁移模块

提供数据库的首次建表、Schema 迁移和版本管理功能。
支持两种建表方式：
1. 通过 ORM 模型自动建表（推荐用于开发/测试）
2. 通过 SQL 文件执行建表（推荐用于生产，与 schema.sql 保持一致）
"""

from pathlib import Path

from sqlalchemy import inspect, text

from src.core.database.database_manager import DatabaseManager, get_db_manager
from src.core.logging import get_logger
from src.data.models.base import Base

logger = get_logger(__name__)

EXPECTED_TABLES = [
    "space",
    "environment",
    "endpoint",
    "test_run",
    "test_case",
    "test_result",
    "test_summary",
    "report",
    "conversation",
    "message",
    "llm_log",
]


def init_database_from_orm(manager: DatabaseManager | None = None) -> None:
    """
    通过 ORM 模型自动创建所有表

    适用于开发和测试环境快速初始化。
    如果表已存在则跳过。

    Args:
        manager: 数据库管理器实例，为 None 时使用全局单例
    """
    mgr = manager or get_db_manager()
    Base.metadata.create_all(mgr.engine)
    _create_views(mgr)
    logger.info("通过ORM模型初始化数据库完成", method="orm")


def init_database_from_sql(
    sql_file: str = "sql/schema.sql",
    manager: DatabaseManager | None = None,
) -> None:
    """
    通过 SQL 文件执行建表

    适用于生产环境，确保与 schema.sql 定义完全一致。

    Args:
        sql_file: SQL 脚本文件路径
        manager: 数据库管理器实例
    """
    mgr = manager or get_db_manager()
    path = Path(sql_file)
    if not path.exists():
        raise FileNotFoundError(f"SQL 文件不存在: {sql_file}")

    sql_content = path.read_text(encoding="utf-8")
    statements = _parse_sql_statements(sql_content)

    with mgr.engine.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.commit()

    logger.info(
        f"通过SQL文件初始化数据库完成: {sql_file}，语句数: {len(statements)}",
        method="sql",
        file=sql_file,
        statement_count=len(statements),
    )


def check_tables_exist(manager: DatabaseManager | None = None) -> list[str]:
    """
    检查哪些预期的表已存在

    Args:
        manager: 数据库管理器实例

    Returns:
        List[str]: 已存在的表名列表
    """
    mgr = manager or get_db_manager()
    inspector = inspect(mgr.engine)
    existing = inspector.get_table_names()
    return [t for t in EXPECTED_TABLES if t in existing]


def get_missing_tables(manager: DatabaseManager | None = None) -> list[str]:
    """
    获取尚未创建的表

    Args:
        manager: 数据库管理器实例

    Returns:
        List[str]: 缺失的表名列表
    """
    existing = check_tables_exist(manager)
    return [t for t in EXPECTED_TABLES if t not in existing]


def is_database_ready(manager: DatabaseManager | None = None) -> bool:
    """
    判断数据库是否已完整初始化（所有表均存在）

    Args:
        manager: 数据库管理器实例

    Returns:
        bool: 所有预期的表均存在时返回 True
    """
    return len(get_missing_tables(manager)) == 0


def ensure_database(
    db_url: str = "sqlite:///db/TestAgents.db",
    echo: bool = False,
    use_sql_file: bool = False,
    sql_file: str = "sql/schema.sql",
) -> DatabaseManager:
    """
    确保数据库已初始化的一站式便捷函数

    如果数据库未初始化则自动建表；如果已存在则跳过。

    Args:
        db_url: 数据库连接 URL
        echo: 是否输出 SQL 语句
        use_sql_file: 是否使用 SQL 文件建表
        sql_file: SQL 脚本文件路径

    Returns:
        DatabaseManager: 已就绪的数据库管理器
    """
    mgr = get_db_manager()
    mgr.initialize(db_url=db_url, echo=echo)

    if not is_database_ready(mgr):
        missing = get_missing_tables(mgr)
        logger.info(f"数据库缺失表: {missing}", tables=missing)

        if use_sql_file:
            init_database_from_sql(sql_file, mgr)
        else:
            init_database_from_orm(mgr)

        logger.info("数据库初始化完成", action="setup_complete")
    else:
        logger.debug("数据库已就绪，无需初始化", action="already_ready")

    return mgr


def _create_views(manager: DatabaseManager) -> None:
    """创建分析视图（仅 ORM 建表模式下调用）"""
    views = [
        """
        CREATE VIEW IF NOT EXISTS v_run_overview AS
        SELECT
            tr.id           AS run_id,
            p.name          AS space_name,
            e.name          AS environment_name,
            tr.status       AS run_status,
            tr.trigger_type,
            tr.llm_provider,
            tr.llm_model,
            ts.total, ts.passed, ts.failed, ts.skipped, ts.error,
            ts.pass_rate, ts.avg_response_time, ts.p95_response_time,
            ts.total_duration,
            tr.started_at, tr.finished_at, tr.created_at
        FROM test_run tr
        LEFT JOIN space      p  ON tr.space_id     = p.id
        LEFT JOIN environment  e  ON tr.environment_id  = e.id
        LEFT JOIN test_summary ts ON ts.run_id          = tr.id
        """,
        """
        CREATE VIEW IF NOT EXISTS v_api_pass_rate AS
        SELECT
            tr.request_url, tr.request_method,
            COUNT(*)                                                AS total_executions,
            SUM(CASE WHEN tr.status = 'passed' THEN 1 ELSE 0 END) AS passed_count,
            SUM(CASE WHEN tr.status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
            ROUND(SUM(CASE WHEN tr.status = 'passed' THEN 1.0 ELSE 0 END)
                  / NULLIF(COUNT(*), 0) * 100, 2)                  AS pass_rate,
            ROUND(AVG(tr.response_time), 2)                        AS avg_response_time,
            ROUND(MIN(tr.response_time), 2)                        AS min_response_time,
            ROUND(MAX(tr.response_time), 2)                        AS max_response_time
        FROM test_result tr
        WHERE tr.status IN ('passed','failed')
        GROUP BY tr.request_url, tr.request_method
        """,
        """
        CREATE VIEW IF NOT EXISTS v_scenario_distribution AS
        SELECT
            tc.scenario_type,
            COUNT(*)                                                AS total_cases,
            SUM(CASE WHEN tr.status = 'passed' THEN 1 ELSE 0 END) AS passed,
            SUM(CASE WHEN tr.status = 'failed' THEN 1 ELSE 0 END) AS failed,
            SUM(CASE WHEN tr.status = 'error'  THEN 1 ELSE 0 END) AS errors,
            ROUND(SUM(CASE WHEN tr.status = 'passed' THEN 1.0 ELSE 0 END)
                  / NULLIF(SUM(CASE WHEN tr.status IN ('passed','failed') THEN 1 ELSE 0 END), 0) * 100, 2)
                                                                    AS pass_rate
        FROM test_case tc
        LEFT JOIN test_result tr ON tr.test_case_id = tc.id
        GROUP BY tc.scenario_type
        """,
    ]

    with manager.engine.connect() as conn:
        for view_sql in views:
            conn.execute(text(view_sql))
        conn.commit()


def _parse_sql_statements(sql_content: str) -> list[str]:
    """
    将 SQL 文件内容解析为独立的 SQL 语句列表

    处理 TRIGGER / VIEW 等包含多个分号的复合语句。
    """
    results: list[str] = []
    current: list[str] = []
    in_trigger = False

    for line in sql_content.split("\n"):
        stripped = line.strip()

        if not stripped or stripped.startswith("--"):
            continue

        if stripped.upper().startswith("CREATE TRIGGER"):
            in_trigger = True

        current.append(line)

        if in_trigger and stripped.upper().startswith("END;"):
            results.append("\n".join(current))
            current = []
            in_trigger = False
        elif not in_trigger and ";" in stripped:
            statement = "\n".join(current).strip().rstrip(";").strip()
            if statement:
                results.append(statement)
            current = []

    if current:
        statement = "\n".join(current).strip().rstrip(";").strip()
        if statement:
            results.append(statement)

    return results
