"""结构化日志管理模块。

基于 structlog 与标准库 logging 双输出：控制台按配置渲染彩色文本或 JSON，
文件固定 JSON 并按大小轮转。
"""

import logging
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from structlog.typing import FilteringBoundLogger


class StructLogConfig:
    """日志系统默认配置，均为类属性，运行时不再变更。"""

    #: 日志目录；相对路径按进程 cwd 解析
    LOG_DIR: str = "logs"

    #: 日志文件名模板，``{timestamp}`` 替换为会话开始时间
    LOG_FILE_FORMAT: str = "structlog_{timestamp}.log"

    #: 标准库日志行格式
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    #: 日志时间戳格式
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

    LOG_TO_CONSOLE: bool = True

    LOG_TO_FILE: bool = True

    LOG_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 5


class StructLogger:
    """结构化日志记录器。

    进程内单例：``setup_logging`` 由 ``_setup_lock`` 保护且只执行一次，
    各模块通过 ``get_logger`` 共用同一套 handler 与 structlog 配置。
    """

    _loggers: dict = {}
    _log_file_path: str | None = None
    _session_start_time: str | None = None
    _setup_lock = threading.Lock()
    _initialized: bool = False
    _log_level: int | None = None
    _debug: bool = False

    @classmethod
    def setup_logging(cls, log_level: str | None = None) -> None:
        """初始化全局日志系统，重复调用直接返回。

        副作用：清空 root logger 的 handler，创建日志目录与日志文件，
        并覆盖 structlog 全局配置。

        Args:
            log_level: 日志级别名；None 时取配置文件中的 ``logging.level``
        """
        with cls._setup_lock:
            if cls._initialized:
                return

            # 延迟导入，避免 src/__init__.py 与 config、logging 之间的循环依赖
            from src.core.config import get_config

            settings = get_config()
            cls._debug = getattr(settings.logging, "format", "console") == "console"

            if log_level is None:
                log_level = settings.logging.level.upper()
            log_level = cls._validate_log_level(log_level)
            cls._log_level = getattr(logging, log_level)

            log_dir = Path(StructLogConfig.LOG_DIR)
            log_dir.mkdir(parents=True, exist_ok=True)

            # 文件名沿用本进程首次初始化的时间，重启后才换新文件
            if cls._session_start_time is None:
                cls._session_start_time = datetime.now().strftime("%Y%m%d_%H%M%S")

            log_filename = StructLogConfig.LOG_FILE_FORMAT.replace("{timestamp}", cls._session_start_time)
            cls._log_file_path = str(log_dir / log_filename)

            cls._setup_stdlib_logging()

            cls._setup_structlog()

            cls._initialized = True

    @classmethod
    def _validate_log_level(cls, log_level: str) -> str:
        """校验日志级别名，非法值回退为 ``INFO`` 并记录告警。

        Args:
            log_level: 日志级别字符串，大小写不敏感

        Returns:
            规范化后的级别名
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        log_level = log_level.upper()
        if log_level not in valid_levels:
            logging.warning("无效的日志级别 '%s'，使用默认值 'INFO'", log_level)
            return "INFO"
        return log_level

    @classmethod
    def _setup_stdlib_logging(cls) -> None:
        """构建 root logger 的 handler 集合：控制台与轮转文件。

        副作用：清空 root logger 现有 handler 后重新挂载。
        """
        log_level = cls._log_level or logging.INFO
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(log_level)

        if cls._debug:
            console_formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.dev.ConsoleRenderer(colors=True),
                foreign_pre_chain=cls._get_shared_processors(),
            )
        else:
            # ensure_ascii=False 保证中文不被转义为 Unicode 转义序列
            console_formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer(ensure_ascii=False),
                foreign_pre_chain=cls._get_shared_processors(),
            )

        # 文件始终写 JSON，便于离线解析
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(ensure_ascii=False),
            foreign_pre_chain=cls._get_shared_processors(),
        )

        if StructLogConfig.LOG_TO_CONSOLE:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

        if StructLogConfig.LOG_TO_FILE and cls._log_file_path:
            file_handler = RotatingFileHandler(
                filename=cls._log_file_path,
                maxBytes=StructLogConfig.LOG_MAX_BYTES,
                backupCount=StructLogConfig.LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

    @classmethod
    def _setup_structlog(cls) -> None:
        """配置 structlog 全局处理器链，末端交由标准库 handler 渲染。

        副作用：覆盖 structlog 进程级配置。
        """
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.UnicodeDecoder(),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

    @classmethod
    def _get_shared_processors(cls) -> list:
        """返回标准库日志转入 structlog 渲染前的共享处理器链。

        Returns:
            处理器列表，按执行顺序排列
        """
        return [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
        ]

    @classmethod
    def get_logger(cls, name: str | None = None) -> "FilteringBoundLogger":
        """获取指定名称的结构化 logger，未初始化时先完成初始化。

        Args:
            name: logger 名称，通常传模块名；None 取 ``root``

        Returns:
            已绑定的 structlog logger，同名实例在进程内复用
        """
        if not cls._initialized:
            cls.setup_logging()

        logger_name = name or "root"

        # 字典的读改写需在同一把锁内完成
        with cls._setup_lock:
            if logger_name not in cls._loggers:
                logger = structlog.get_logger(logger_name)
                cls._loggers[logger_name] = logger

            return cls._loggers[logger_name]

    @classmethod
    def get_log_file_path(cls) -> str | None:
        """返回当前会话的日志文件路径；未初始化时为 None。"""
        return cls._log_file_path

    @classmethod
    def reset(cls) -> None:
        """重置日志系统状态，仅供测试使用。

        副作用：清空 root logger 的 handler 并重置 structlog 全局配置。
        """
        with cls._setup_lock:
            cls._loggers.clear()
            cls._log_file_path = None
            cls._session_start_time = None
            cls._initialized = False
            cls._log_level = None
            cls._debug = False

            root_logger = logging.getLogger()
            root_logger.handlers.clear()

            structlog.reset_defaults()


def setup_logging(log_level: str | None = None) -> None:
    """初始化全局日志系统。

    Args:
        log_level: 日志级别名；None 时取配置文件中的设置
    """
    StructLogger.setup_logging(log_level)


def get_logger(name: str | None = None) -> "FilteringBoundLogger":
    """获取结构化日志记录器。

    Args:
        name: logger 名称；None 取 ``root``

    Returns:
        已绑定的 structlog logger
    """
    return StructLogger.get_logger(name)


def log_execution_time(name: str | None = None, level: str = "info", log_args: bool = False):
    """记录被装饰函数执行耗时的装饰器。

    Args:
        name: 日志中的函数名；None 时取 ``func.__name__``
        level: 日志级别方法名，取值 ``debug`` / ``info`` / ``warning`` / ``error``
        log_args: 是否把位置参数与关键字参数一并写入日志

    Returns:
        被包装后的函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger()
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                execution_time = time.perf_counter() - start_time
                log_kwargs = {
                    "function_name": name or func.__name__,
                    "execution_time_seconds": round(execution_time, 4),
                    "execution_time_ms": round(execution_time * 1000, 2),
                }
                if log_args:
                    log_kwargs["args"] = args
                    log_kwargs["kwargs"] = kwargs

                getattr(logger, level)("method_execution_complete", **log_kwargs)

        return wrapper

    return decorator
