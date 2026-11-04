"""v2 迁移：旧 schema 升级到 Agent 平台 schema。

补列、重建 ``conversation`` 表、归一化 ``mode`` 取值。SQLite 不能修改既有 CHECK 约束，
只能重建表；重建时须关闭外键，否则 ``DROP TABLE`` 的隐式删除会级联清空 message 行。
全部步骤幂等，可重复执行。
"""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from src.core.logging import get_logger
from src.data.models.base import Base

logger = get_logger(__name__)

_LEGACY_MODE_MAP = {"Run": "agent", "Ask": "ask", "Plan": "plan"}

_CONVERSATION_DDL = """
CREATE TABLE conversation__v2 (
    id INTEGER NOT NULL PRIMARY KEY,
    space_id INTEGER REFERENCES space(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT 'agent',
    skill_names TEXT NOT NULL DEFAULT '[]',
    environment_id INTEGER REFERENCES environment(id) ON DELETE SET NULL,
    status INTEGER NOT NULL DEFAULT 1,
    last_message_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CONSTRAINT ck_conversation_mode CHECK (mode IN ('agent','ask','plan')),
    CONSTRAINT ck_conversation_status CHECK (status IN (0,1))
)
"""

# 补列：(表, 列, 列定义)
_ADDED_COLUMNS = [
    ("space", "workspace_path", "TEXT NOT NULL DEFAULT ''"),
    ("environment", "is_production", "INTEGER NOT NULL DEFAULT 0"),
    ("conversation", "skill_names", "TEXT NOT NULL DEFAULT '[]'"),
    ("conversation", "environment_id", "INTEGER DEFAULT NULL"),
    # llm_log 的成本归因维度
    ("llm_log", "space_id", "INTEGER DEFAULT NULL"),
    ("llm_log", "conversation_id", "INTEGER DEFAULT NULL"),
    ("llm_log", "routing_tier", "TEXT NOT NULL DEFAULT ''"),
    ("llm_log", "cost_usd", "REAL DEFAULT NULL"),
]

# 补索引：(索引名, 表, 列清单)
# ``create_all`` 不会为已存在的表补索引，老库升级后的索引在此创建
_ADDED_INDEXES = [
    ("idx_llm_log_space", "llm_log", "space_id, created_at"),
    ("idx_llm_log_conversation", "llm_log", "conversation_id, created_at"),
]


def migrate_v2(engine: Engine) -> None:
    """执行 v2 迁移，幂等，可重复调用。

    仅实现 SQLite 路径，其他方言只记录告警后返回。

    副作用：建表、改列、建索引、回填数据，各步骤自行提交事务。

    Args:
        engine: 目标数据库引擎
    """
    if engine.dialect.name != "sqlite":
        logger.warning("v2 迁移仅实现 SQLite 路径，跳过", dialect=engine.dialect.name)
        return

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    # create_all 只建缺失的表、不改动已有表，可安全放在重建之前
    _create_missing_tables(engine)

    if "conversation" in tables and _has_legacy_mode_check(engine):
        _rebuild_conversation(engine)

    _add_missing_columns(engine)
    _add_missing_indexes(engine)
    _backfill(engine)

    logger.info("v2 迁移完成")


def _create_missing_tables(engine: Engine) -> None:
    """按 ORM 模型创建缺失的表。

    Args:
        engine: 目标数据库引擎
    """
    Base.metadata.create_all(engine)


# 步骤


def _has_legacy_mode_check(engine: Engine) -> bool:
    """判断 ``conversation`` 是否仍带旧的三值 ``mode`` CHECK。

    Args:
        engine: 目标数据库引擎

    Returns:
        列定义中含 ``Run`` 取值时返回 True
    """
    with engine.connect() as conn:
        ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'conversation'")
        ).scalar()

    if not ddl:
        return False
    # 旧约束含 'Run'，新约束只有 agent/ask/plan
    return "'Run'" in ddl or '"Run"' in ddl


def _rebuild_conversation(engine: Engine) -> None:
    """重建 ``conversation`` 表并搬迁数据。

    必须用 raw connection 手动关闭外键：SQLAlchemy 的连接事件在每次 connect 时
    重新打开 ``foreign_keys``，``engine.connect()`` 无法保持关闭，
    而 ``DROP TABLE`` 会触发外键级联删除 message 行。

    副作用：建临时表、搬数据、删旧表、改名并提交；失败时回滚。

    Args:
        engine: 目标数据库引擎

    Raises:
        Exception: 重建过程中的任何失败，回滚后原样抛出
    """
    raw = engine.raw_connection()
    old_columns = {c["name"] for c in inspect(engine).get_columns("conversation")}

    try:
        cursor = raw.cursor()
        # 清理上一轮中断可能残留的临时表
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("DROP TABLE IF EXISTS conversation__v2")
        cursor.execute(_CONVERSATION_DDL)

        new_columns = [
            "id",
            "space_id",
            "title",
            "mode",
            "skill_names",
            "environment_id",
            "status",
            "last_message_at",
            "created_at",
            "updated_at",
        ]
        select_exprs = []
        for column in new_columns:
            if column == "mode":
                select_exprs.append(_mode_case_sql())
            elif column == "skill_names":
                select_exprs.append("'[]'" if "skill_names" not in old_columns else "COALESCE(skill_names, '[]')")
            elif column == "environment_id":
                select_exprs.append("NULL")
            elif column in old_columns:
                select_exprs.append(column)
            else:
                select_exprs.append("NULL")

        cursor.execute(
            f"INSERT INTO conversation__v2 ({', '.join(new_columns)}) "
            f"SELECT {', '.join(select_exprs)} FROM conversation"
        )
        cursor.execute("DROP TABLE conversation")
        cursor.execute("ALTER TABLE conversation__v2 RENAME TO conversation")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversation_space ON conversation(space_id)")
        cursor.execute("PRAGMA foreign_keys=ON")
        raw.commit()
        logger.info("conversation 表已重建（mode 归一化为 agent/ask/plan）")
    except Exception:
        raw.rollback()
        logger.error("conversation 表重建失败，已回滚")
        raise
    finally:
        raw.close()


def _mode_case_sql() -> str:
    """生成把旧 ``mode`` 值映射为新值的 SQL CASE 表达式。

    Returns:
        CASE 表达式字符串，未匹配的取值回退为 ``agent``
    """
    branches = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in _LEGACY_MODE_MAP.items())
    return f"CASE mode {branches} ELSE 'agent' END"


def _add_missing_columns(engine: Engine) -> None:
    """按需补列。

    SQLite 的 ``ADD COLUMN`` 不支持 ``IF NOT EXISTS``，需先查后加。

    副作用：写库并逐列提交。

    Args:
        engine: 目标数据库引擎
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    for table, column, definition in _ADDED_COLUMNS:
        if table not in tables:
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column in existing:
            continue
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        logger.info("已补列", table=table, column=column)


def _add_missing_indexes(engine: Engine) -> None:
    """按需补索引，``CREATE INDEX IF NOT EXISTS`` 本身幂等。

    副作用：写库并提交。

    Args:
        engine: 目标数据库引擎
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    for name, table, columns in _ADDED_INDEXES:
        if table not in tables:
            continue
        with engine.begin() as conn:
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})"))


def _backfill(engine: Engine) -> None:
    """回填历史数据：``workspace_path`` 默认值、``mode`` 归一化、``skill_names`` 空值。

    副作用：写库并提交。

    Args:
        engine: 目标数据库引擎
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        if "space" in tables:
            conn.execute(
                text(
                    "UPDATE space SET workspace_path = 'workspaces/' || id "
                    "WHERE workspace_path IS NULL OR workspace_path = ''"
                )
            )

        if "conversation" in tables:
            for old, new in _LEGACY_MODE_MAP.items():
                conn.execute(
                    text("UPDATE conversation SET mode = :new WHERE mode = :old"),
                    {"new": new, "old": old},
                )
            conn.execute(
                text("UPDATE conversation SET skill_names = '[]' WHERE skill_names IS NULL OR skill_names = ''")
            )

    logger.debug("v2 数据回填完成")
