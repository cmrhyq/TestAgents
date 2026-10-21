"""v2 迁移：旧 schema -> Agent 平台 schema。

要解决三件事：

1. **补列**：``space.workspace_path``、``environment.is_production``、
   ``conversation.skill_names`` / ``environment_id``
2. **重建 conversation 表**：旧表有 ``CHECK (mode IN ('Ask','Plan','Run'))``，
   SQLite 不支持修改约束，只能重建。重建时必须临时关掉外键——否则
   ``DROP TABLE`` 的隐式 ``DELETE FROM`` 会级联把 message 行一起删掉。
3. **数据归一化**：``Run``->``agent``、``Ask``->``ask``、``Plan``->``plan``

全部操作幂等：重复执行不会报错，也不会重复改数据。
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
    # llm_log 的成本归因维度（v1.0 补：此前无法按空间/会话聚合）
    ("llm_log", "space_id", "INTEGER DEFAULT NULL"),
    ("llm_log", "conversation_id", "INTEGER DEFAULT NULL"),
    ("llm_log", "routing_tier", "TEXT NOT NULL DEFAULT ''"),
    ("llm_log", "cost_usd", "REAL DEFAULT NULL"),
]

# 补索引：(索引名, 表, 列清单)
# create_all 不会给**已存在**的表加索引，老库补列后索引必须在这里补。
_ADDED_INDEXES = [
    ("idx_llm_log_space", "llm_log", "space_id, created_at"),
    ("idx_llm_log_conversation", "llm_log", "conversation_id, created_at"),
]


def migrate_v2(engine: Engine) -> None:
    """执行 v2 迁移（幂等）。"""
    if engine.dialect.name != "sqlite":
        logger.warning("v2 迁移仅实现 SQLite 路径，跳过", dialect=engine.dialect.name)
        return

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    # 先建缺失的表（新表：space_memory / knowledge_* / skill）。
    # create_all 只创建不存在的表，不会动已有表，因此可以安全地放在重建之前。
    _create_missing_tables(engine)

    if "conversation" in tables and _has_legacy_mode_check(engine):
        _rebuild_conversation(engine)

    _add_missing_columns(engine)
    _add_missing_indexes(engine)
    _backfill(engine)

    logger.info("v2 迁移完成")


def _create_missing_tables(engine: Engine) -> None:
    """按 ORM 模型创建缺失的表。"""
    Base.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# 步骤
# ---------------------------------------------------------------------------


def _has_legacy_mode_check(engine: Engine) -> bool:
    """判断 conversation 是否带着旧的三值 CHECK。"""
    with engine.connect() as conn:
        ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'conversation'")
        ).scalar()

    if not ddl:
        return False
    # 旧约束里含 'Run'；新约束只有 agent/ask/plan
    return "'Run'" in ddl or '"Run"' in ddl


def _rebuild_conversation(engine: Engine) -> None:
    """重建 conversation 表并迁移数据。

    必须走 raw connection 手动关外键：SQLAlchemy 的连接事件会在每次
    connect 时把 ``foreign_keys`` 打开，走 ``engine.connect()`` 关不掉。
    """
    raw = engine.raw_connection()
    old_columns = {c["name"] for c in inspect(engine).get_columns("conversation")}

    try:
        cursor = raw.cursor()
        # 新建的表与旧表同名会冲突，先确保上一轮中断没留下残骸
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
    """把旧 mode 值映射为新值的 SQL CASE 表达式。"""
    branches = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in _LEGACY_MODE_MAP.items())
    return f"CASE mode {branches} ELSE 'agent' END"


def _add_missing_columns(engine: Engine) -> None:
    """按需补列（SQLite 的 ADD COLUMN 不支持 IF NOT EXISTS，先查后加）。"""
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
    """按需补索引（``CREATE INDEX IF NOT EXISTS`` 本身幂等）。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    for name, table, columns in _ADDED_INDEXES:
        if table not in tables:
            continue
        with engine.begin() as conn:
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})"))


def _backfill(engine: Engine) -> None:
    """回填历史数据。"""
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
