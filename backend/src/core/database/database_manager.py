"""
数据库连接管理模块

提供 SQLAlchemy 引擎创建、会话管理和连接池功能。
使用线程安全的单例模式确保全局唯一的数据库连接。
"""

import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src import AppConfig, get_config
from src.core.logging import get_logger
from src.data.models.base import Base

logger = get_logger(__name__)


class DatabaseManager:
    """
    数据库连接管理器

    线程安全的单例类，负责：
    - 创建和管理 SQLAlchemy 引擎
    - 配置连接池参数
    - 提供会话工厂和上下文管理器
    - SQLite WAL 模式和外键约束的自动启用
    """

    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        """获取 DatabaseManager 单例实例（双重检查锁定）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def initialize(
        self,
        db_url: str = "sqlite:///db/TestAgents.db",
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
    ) -> None:
        """
        初始化数据库引擎和会话工厂

        Args:
            db_url: 数据库连接 URL
            echo: 是否输出 SQL 语句到日志
            pool_size: 连接池大小（SQLite 忽略此参数）
            max_overflow: 最大溢出连接数（SQLite 忽略此参数）
            pool_timeout: 连接池获取超时（秒）
            pool_recycle: 连接回收时间（秒）
        """
        if self._initialized:
            logger.debug("数据库已初始化，跳过重复初始化", action="initialize")
            return

        self._ensure_db_directory(db_url)

        engine_kwargs: dict = {"echo": echo}

        if db_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs.update(
                {
                    "pool_size": pool_size,
                    "max_overflow": max_overflow,
                    "pool_timeout": pool_timeout,
                    "pool_recycle": pool_recycle,
                }
            )

        self._engine = create_engine(db_url, **engine_kwargs)

        if db_url.startswith("sqlite"):
            self._configure_sqlite_pragmas(self._engine)

        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        self._initialized = True
        logger.info(f"数据库初始化完成: {self._mask_url(db_url)}", db_url=self._mask_url(db_url))

    @staticmethod
    def _ensure_db_directory(db_url: str) -> None:
        """确保 SQLite 数据库文件所在的目录存在"""
        if not db_url.startswith("sqlite:///"):
            return
        db_path = db_url.replace("sqlite:///", "")
        parent = Path(db_path).parent
        parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _configure_sqlite_pragmas(engine: Engine) -> None:
        """为每个 SQLite 连接启用 WAL 模式和外键约束"""

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA encoding='UTF-8'")
            cursor.close()

    @staticmethod
    def _mask_url(url: str) -> str:
        """对数据库 URL 中的敏感信息脱敏"""
        if "@" in url:
            protocol_end = url.index("://") + 3
            at_pos = url.index("@")
            return url[:protocol_end] + "***:***" + url[at_pos:]
        return url

    @property
    def engine(self) -> Engine:
        """获取 SQLAlchemy 引擎"""
        self._check_initialized()
        return self._engine  # type: ignore[return-value]

    @property
    def session_factory(self) -> sessionmaker:
        """获取会话工厂"""
        self._check_initialized()
        return self._session_factory  # type: ignore[return-value]

    def create_session(self) -> Session:
        """创建一个新的数据库会话"""
        self._check_initialized()
        return self._session_factory()  # type: ignore[misc]

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        获取数据库会话的上下文管理器

        自动处理提交和回滚：
        - 正常退出时自动提交
        - 发生异常时自动回滚并重新抛出异常
        """
        session = self.create_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_tables(self) -> None:
        """根据 ORM 模型创建所有表（如果不存在）"""
        self._check_initialized()
        Base.metadata.create_all(self._engine)  # type: ignore[arg-type]
        logger.info("数据库表已创建", action="create_tables")

    def drop_tables(self) -> None:
        """删除所有 ORM 模型对应的表（仅用于测试环境）"""
        self._check_initialized()
        Base.metadata.drop_all(self._engine)  # type: ignore[arg-type]
        logger.warning("数据库表已删除（仅测试环境）", action="drop_tables")

    def execute_sql_file(self, sql_file_path: str) -> None:
        """
        执行 SQL 文件中的所有语句

        Args:
            sql_file_path: SQL 文件路径
        """
        self._check_initialized()
        path = Path(sql_file_path)
        if not path.exists():
            raise FileNotFoundError(f"SQL 文件不存在: {sql_file_path}")

        sql_content = path.read_text(encoding="utf-8")
        statements = [
            stmt.strip() for stmt in sql_content.split(";") if stmt.strip() and not stmt.strip().startswith("--")
        ]

        with self._engine.connect() as conn:  # type: ignore[union-attr]
            for statement in statements:
                if statement:
                    conn.execute(text(statement))
            conn.commit()

        logger.info(
            f"SQL文件执行完成: {sql_file_path}，语句数: {len(statements)}",
            file=sql_file_path,
            statements=len(statements),
        )

    def check_connection(self) -> bool:
        """
        验证数据库连接是否正常

        Returns:
            bool: 连接正常返回 True，否则返回 False
        """
        try:
            self._check_initialized()
            with self._engine.connect() as conn:  # type: ignore[union-attr]
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"数据库连接检查失败: {str(e)}", error=str(e))
            return False

    def close(self) -> None:
        """关闭数据库引擎并释放所有连接"""
        if self._engine is not None:
            self._engine.dispose()
            logger.info("数据库引擎已释放", action="dispose")
        self._engine = None
        self._session_factory = None
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """数据库是否已初始化"""
        return self._initialized

    def _check_initialized(self) -> None:
        """检查数据库是否已初始化"""
        if not self._initialized:
            raise RuntimeError("数据库尚未初始化，请先调用 DatabaseManager.get_instance().initialize()")

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例（仅用于测试）"""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None


def get_db_manager() -> DatabaseManager:
    """获取 DatabaseManager 实例的便捷函数"""
    return DatabaseManager.get_instance()


def init_database(
    db_url: str = "sqlite:///db/TestAgents.db",
    echo: bool = False,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_timeout: int = 30,
    pool_recycle: int = 3600,
) -> DatabaseManager:
    """
    初始化数据库的便捷函数

    Args:
        db_url: 数据库连接 URL
        echo: 是否输出 SQL 语句
        pool_size: 连接池大小
        max_overflow: 最大溢出连接数
        pool_timeout: 连接池获取超时（秒）
        pool_recycle: 连接回收时间（秒）

    Returns:
        DatabaseManager: 已初始化的数据库管理器实例
    """
    manager = get_db_manager()
    manager.initialize(
        db_url=db_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
    )
    return manager


def init_database_from_config(config: AppConfig | None = None) -> DatabaseManager:
    """
    从配置中初始化数据库并返回session
    Args:
        config: 系统配置

    Returns:
        DatabaseManager: DatabaseManager
    """
    config = config or get_config()
    manager = get_db_manager()
    manager.initialize(
        db_url=config.database.url,
        echo=config.database.echo,
        pool_size=config.database.pool_size,
        max_overflow=config.database.max_overflow,
        pool_timeout=config.database.pool_timeout,
        pool_recycle=config.database.pool_recycle,
    )
    return manager


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """获取数据库会话的全局便捷函数"""
    manager = get_db_manager()
    with manager.get_session() as session:
        yield session
