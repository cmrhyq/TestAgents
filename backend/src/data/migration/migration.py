"""数据库初始化与迁移。

提供首次建表、Schema 迁移与版本管理。建表有两种方式：ORM 模型自动建表（开发与
测试）与 SQL 文件建表（生产，与 ``schema.sql`` 保持一致）。
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
    "agent_run",
    "agent_tool_call",
    "report",
    "conversation",
    "message",
    "llm_log",
    # v2 新增表
    "space_memory",
    "knowledge_document",
    "knowledge_chunk",
    "skill",
]


def init_database_from_orm(manager: DatabaseManager | None = None) -> None:
    """按 ORM 模型建表，随后执行 v2 / v3 迁移与视图创建。

    表已存在时跳过建表；迁移本身幂等，可重复执行。

    副作用：写库并提交（``create_all`` 与迁移各自管理事务）。

    Args:
        manager: 数据库管理器；None 时使用全局单例
    """
    mgr = manager or get_db_manager()
    Base.metadata.create_all(mgr.engine)

    # 延迟导入：避免 migration 模块循环依赖
    from src.data.migration.v2_agent_migration import migrate_v2
    from src.data.migration.v3_agent_run_migration import migrate_v3

    migrate_v2(mgr.engine)
    migrate_v3(mgr.engine)

    _create_views(mgr)
    logger.info("通过ORM模型初始化数据库完成", method="orm")


def init_database_from_sql(
    sql_file: str = "sql/schema.sql",
    manager: DatabaseManager | None = None,
) -> None:
    """按 SQL 文件逐条执行建表语句，事务在全部语句执行后提交。

    副作用：写库并提交，部分语句失败时已执行的语句仍可能留下。

    Args:
        sql_file: SQL 脚本路径，相对当前工作目录
        manager: 数据库管理器；None 时使用全局单例

    Raises:
        FileNotFoundError: SQL 文件不存在
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
    """返回 ``EXPECTED_TABLES`` 中已存在的表名。

    Args:
        manager: 数据库管理器；None 时使用全局单例

    Returns:
        已存在的表名列表，顺序与 ``EXPECTED_TABLES`` 一致
    """
    mgr = manager or get_db_manager()
    inspector = inspect(mgr.engine)
    existing = inspector.get_table_names()
    return [t for t in EXPECTED_TABLES if t in existing]


def get_missing_tables(manager: DatabaseManager | None = None) -> list[str]:
    """返回尚未创建的表名。

    Args:
        manager: 数据库管理器；None 时使用全局单例

    Returns:
        缺失的表名列表
    """
    existing = check_tables_exist(manager)
    return [t for t in EXPECTED_TABLES if t not in existing]


def is_database_ready(manager: DatabaseManager | None = None) -> bool:
    """判断数据库是否已完整初始化。

    Args:
        manager: 数据库管理器；None 时使用全局单例

    Returns:
        所有预期表均存在时返回 True
    """
    return len(get_missing_tables(manager)) == 0


def ensure_database(
    db_url: str = "sqlite:///db/TestAgents.db",
    echo: bool = False,
    use_sql_file: bool = False,
    sql_file: str = "sql/schema.sql",
) -> DatabaseManager:
    """确保数据库就绪：缺表时建表，已就绪时跳过。

    副作用：必要时建表、执行迁移并写库；已就绪时不产生写操作。

    Args:
        db_url: 数据库连接 URL
        echo: 是否输出 SQL 语句
        use_sql_file: 为 True 时按 SQL 文件建表，否则按 ORM 建表
        sql_file: SQL 脚本路径，仅在 ``use_sql_file`` 为 True 时使用

    Returns:
        就绪的数据库管理器
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
    """创建分析视图，仅 ORM 建表模式下调用。

    必须先 ``DROP VIEW`` 再 ``CREATE``：SQLite 不会更新已存在的视图定义，
    旧定义会一直生效并指向已改名的表。

    副作用：写库并提交。
    """
    views = {
        "v_run_overview": """
            SELECT
                r.id            AS run_id,
                s.name          AS space_name,
                e.name          AS environment_name,
                r.status        AS run_status,
                r.mode,
                r.title,
                r.tool_call_count,
                r.ok_count,
                r.error_count,
                r.success_rate,
                r.avg_response_time,
                r.duration_ms,
                r.llm_call_count,
                r.total_tokens,
                r.cost_usd,
                r.started_at, r.finished_at, r.created_at
            FROM agent_run r
            LEFT JOIN space       s ON r.space_id       = s.id
            LEFT JOIN environment e ON r.environment_id = e.id
        """,
        # 工具维度统计
        "v_tool_call_stats": """
            SELECT
                tool_name,
                tool_type,
                COUNT(*)                                                  AS total_calls,
                SUM(CASE WHEN ok = 1 THEN 1 ELSE 0 END)                   AS ok_calls,
                SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END)                   AS error_calls,
                ROUND(SUM(CASE WHEN ok = 1 THEN 1.0 ELSE 0 END)
                      / NULLIF(COUNT(*), 0) * 100, 2)                     AS success_rate,
                ROUND(AVG(duration_ms), 2)                                AS avg_response_time,
                MIN(duration_ms)                                          AS min_response_time,
                MAX(duration_ms)                                          AS max_response_time
            FROM agent_tool_call
            GROUP BY tool_name, tool_type
        """,
        # 接口维度统计，成功口径改为 HTTP 状态码
        "v_http_endpoint_stats": """
            SELECT
                http_url,
                http_method,
                COUNT(*)                                                   AS total_executions,
                SUM(CASE WHEN http_status_code BETWEEN 200 AND 299 THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN http_status_code >= 400 OR http_status_code IS NULL THEN 1 ELSE 0 END) AS error_count,
                ROUND(AVG(duration_ms), 2)                                 AS avg_response_time
            FROM agent_tool_call
            WHERE http_url IS NOT NULL AND http_url <> ''
            GROUP BY http_url, http_method
        """,
    }

    with manager.engine.begin() as conn:
        for name, select_sql in views.items():
            conn.execute(text(f"DROP VIEW IF EXISTS {name}"))
            conn.execute(text(f"CREATE VIEW {name} AS {select_sql}"))


def _parse_sql_statements(sql_content: str) -> list[str]:
    """把 SQL 文件内容拆成独立语句。

    ``CREATE TRIGGER`` 体内含分号，需以 ``END;`` 作为语句结束标志；以 ``--`` 开头的行被丢弃。

    Args:
        sql_content: SQL 文件全文

    Returns:
        语句列表，已去除末尾分号与空语句
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
