"""数据库连接管理。

提供 SQLAlchemy 引擎、会话工厂与连接池配置；SQLite 连接自动启用 WAL、外键与写锁等待。
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
    """线程安全的数据库连接管理器单例。

    ``initialize`` 只生效一次，重复调用直接返回；取引擎、会话工厂前会校验初始化状态。
    """

    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        """返回单例实例，以双重检查锁创建。

        Returns:
            全局唯一的管理器实例
        """
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
        """创建引擎与会话工厂，重复调用直接返回。

        副作用：必要时创建 SQLite 数据库文件所在目录，并建立数据库连接。

        Args:
            db_url: 数据库连接 URL
            echo: 是否把 SQL 语句输出到日志
            pool_size: 连接池大小，SQLite 忽略
            max_overflow: 最大溢出连接数，SQLite 忽略
            pool_timeout: 从连接池取连接的超时秒数，SQLite 忽略
            pool_recycle: 连接回收秒数，SQLite 忽略
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
        """确保 SQLite 数据库文件所在目录存在。

        副作用：创建缺失的父目录。

        Args:
            db_url: 数据库连接 URL，非 ``sqlite:///`` 时直接返回
        """
        if not db_url.startswith("sqlite:///"):
            return
        db_path = db_url.replace("sqlite:///", "")
        parent = Path(db_path).parent
        parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _configure_sqlite_pragmas(engine: Engine) -> None:
        """为每个 SQLite 连接启用 WAL、外键约束与写锁等待。

        ``busy_timeout`` 不可省略：WAL 只允许单个写者，多会话并发写会直接抛
        ``database is locked``。

        Args:
            engine: 待挂载 ``connect`` 事件的 SQLAlchemy 引擎
        """

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA encoding='UTF-8'")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    @staticmethod
    def _mask_url(url: str) -> str:
        """隐藏数据库 URL 中的账号与密码。

        Args:
            url: 原始连接 URL

        Returns:
            脱敏后的 URL；不含凭证时原样返回
        """
        if "@" in url:
            protocol_end = url.index("://") + 3
            at_pos = url.index("@")
            return url[:protocol_end] + "***:***" + url[at_pos:]
        return url

    @property
    def engine(self) -> Engine:
        """返回 SQLAlchemy 引擎。

        Raises:
            RuntimeError: 数据库尚未初始化
        """
        self._check_initialized()
        return self._engine  # type: ignore[return-value]

    @property
    def session_factory(self) -> sessionmaker:
        """返回会话工厂。

        Raises:
            RuntimeError: 数据库尚未初始化
        """
        self._check_initialized()
        return self._session_factory  # type: ignore[return-value]

    def create_session(self) -> Session:
        """创建一个新会话，由调用方提交并关闭。

        Returns:
            新的数据库会话

        Raises:
            RuntimeError: 数据库尚未初始化
        """
        self._check_initialized()
        return self._session_factory()  # type: ignore[misc]

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """事务型会话上下文：正常退出提交，异常时回滚并重新抛出。

        退出时总会关闭会话。

        Yields:
            Session: 数据库会话
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
        """按 ORM 模型创建缺失的表。

        副作用：在数据库中执行建表语句。
        """
        self._check_initialized()
        Base.metadata.create_all(self._engine)  # type: ignore[arg-type]
        logger.info("数据库表已创建", action="create_tables")

    def drop_tables(self) -> None:
        """删除所有 ORM 模型对应的表，仅供测试环境。

        副作用：表结构与数据一并丢失。
        """
        self._check_initialized()
        Base.metadata.drop_all(self._engine)  # type: ignore[arg-type]
        logger.warning("数据库表已删除（仅测试环境）", action="drop_tables")

    def execute_sql_file(self, sql_file_path: str) -> None:
        """执行 SQL 文件中的语句。

        文件按 UTF-8 读取，按 ``;`` 切分并跳过以 ``--`` 开头的行。

        副作用：在数据库上执行语句并提交。

        Args:
            sql_file_path: SQL 文件路径

        Raises:
            FileNotFoundError: 文件不存在
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
        """执行 ``SELECT 1`` 探测连接可用性。

        Returns:
            连接可用为 True；异常或未初始化时返回 False
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
        """释放引擎与连接池。

        副作用：关闭所有池内连接，管理器回到未初始化状态。
        """
        if self._engine is not None:
            self._engine.dispose()
            logger.info("数据库引擎已释放", action="dispose")
        self._engine = None
        self._session_factory = None
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """是否已完成初始化。"""
        return self._initialized

    def _check_initialized(self) -> None:
        """校验初始化状态，未初始化时抛出 ``RuntimeError``。

        Raises:
            RuntimeError: 引擎或会话工厂尚未创建
        """
        if not self._initialized:
            raise RuntimeError("数据库尚未初始化，请先调用 DatabaseManager.get_instance().initialize()")

    @classmethod
    def reset_instance(cls) -> None:
        """销毁单例实例，仅供测试使用。

        副作用：先关闭引擎释放连接。
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None


def get_db_manager() -> DatabaseManager:
    """返回数据库管理器单例。

    Returns:
        全局唯一的管理器实例
    """
    return DatabaseManager.get_instance()


def init_database(
    db_url: str = "sqlite:///db/TestAgents.db",
    echo: bool = False,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_timeout: int = 30,
    pool_recycle: int = 3600,
) -> DatabaseManager:
    """按显式参数初始化数据库。

    副作用：建立引擎与连接池。

    Args:
        db_url: 数据库连接 URL
        echo: 是否把 SQL 语句输出到日志
        pool_size: 连接池大小
        max_overflow: 最大溢出连接数
        pool_timeout: 从连接池取连接的超时秒数
        pool_recycle: 连接回收秒数

    Returns:
        已初始化的管理器实例
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
    """按 ``config.database`` 的配置初始化数据库。

    副作用：建立引擎与连接池。

    Args:
        config: 应用配置；None 时取全局配置

    Returns:
        已初始化的管理器实例
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
    """事务型会话上下文，复用单例管理器的连接。

    Yields:
        Session: 数据库会话
    """
    manager = get_db_manager()
    with manager.get_session() as session:
        yield session
