"""
结构化日志管理器模块

该模块基于 structlog 提供结构化日志记录接口，支持：
- 多级别日志记录（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- 双输出（控制台和文件）
- 开发环境彩色输出 / 生产环境 JSON 格式输出
- 日志轮转
- 线程安全
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
    """结构化日志配置类，提供日志相关的默认配置"""

    # 日志目录（相对于空间根目录）
    LOG_DIR: str = "logs"

    # 日志文件格式
    LOG_FILE_FORMAT: str = "structlog_{timestamp}.log"

    # 日志格式（用于文件输出）
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 日志日期格式
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

    # 是否输出到控制台
    LOG_TO_CONSOLE: bool = True

    # 是否输出到文件
    LOG_TO_FILE: bool = True

    # 日志轮转配置
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 单个日志文件最大 10MB
    LOG_BACKUP_COUNT: int = 5  # 保留最近 5 个备份文件


class StructLogger:
    """
    结构化日志记录器类

    提供基于 structlog 的统一日志记录接口，支持：
    - 多级别日志记录（DEBUG, INFO, WARNING, ERROR, CRITICAL）
    - 同时输出到控制台和文件
    - 开发环境：彩色控制台输出
    - 生产环境：JSON 格式输出
    - 日志轮转（按大小和数量限制）
    - 线程安全的初始化
    """

    _loggers: dict = {}
    _log_file_path: str | None = None
    _session_start_time: str | None = None
    _setup_lock = threading.Lock()  # 保护日志系统初始化
    _initialized: bool = False
    _log_level: int | None = None
    _debug: bool = False

    @classmethod
    def setup_logging(cls, log_level: str | None = None) -> None:
        """
        设置结构化日志系统的全局配置（线程安全）

        Args:
            log_level: 日志级别，如果为 None 则使用配置文件中的设置
        """
        with cls._setup_lock:
            # 避免重复初始化
            if cls._initialized:
                return

            # 延迟导入以避免 src/__init__.py 与 config/logging 的循环依赖
            from src.core.config import get_config

            settings = get_config()
            cls._debug = getattr(settings.logging, "format", "console") == "console"

            # 获取并验证日志级别
            if log_level is None:
                log_level = settings.logging.level.upper()
            log_level = cls._validate_log_level(log_level)
            cls._log_level = getattr(logging, log_level)

            # 创建日志目录
            log_dir = Path(StructLogConfig.LOG_DIR)
            log_dir.mkdir(parents=True, exist_ok=True)

            # 生成日志文件名（使用会话开始时间）
            if cls._session_start_time is None:
                cls._session_start_time = datetime.now().strftime("%Y%m%d_%H%M%S")

            log_filename = StructLogConfig.LOG_FILE_FORMAT.replace("{timestamp}", cls._session_start_time)
            cls._log_file_path = str(log_dir / log_filename)

            # 配置标准库 logging
            cls._setup_stdlib_logging()

            # 配置 structlog（使用标准库集成模式）
            cls._setup_structlog()

            cls._initialized = True

    @classmethod
    def _validate_log_level(cls, log_level: str) -> str:
        """
        验证日志级别是否有效

        Args:
            log_level: 日志级别字符串

        Returns:
            str: 有效的日志级别，如果无效则返回默认值 INFO
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        log_level = log_level.upper()
        if log_level not in valid_levels:
            logging.warning("无效的日志级别 '%s'，使用默认值 'INFO'", log_level)
            return "INFO"
        return log_level

    @classmethod
    def _setup_stdlib_logging(cls) -> None:
        """配置标准库 logging"""
        log_level = cls._log_level or logging.INFO
        # 重置 root logger 的 handlers，避免重复配置
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(log_level)

        # 创建格式化器 - 根据环境选择不同的格式化器
        if cls._debug:
            # 开发环境：使用 structlog 的彩色渲染器
            console_formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.dev.ConsoleRenderer(colors=True),
                foreign_pre_chain=cls._get_shared_processors(),
            )
        else:
            # 生产环境：使用 JSON 格式（ensure_ascii=False 保证中文正常显示）
            console_formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer(ensure_ascii=False),
                foreign_pre_chain=cls._get_shared_processors(),
            )

        # 文件格式化器 - 始终使用 JSON 格式便于解析（ensure_ascii=False 保证中文正常显示）
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(ensure_ascii=False),
            foreign_pre_chain=cls._get_shared_processors(),
        )

        # 添加控制台处理器
        if StructLogConfig.LOG_TO_CONSOLE:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

        # 添加文件处理器（使用 RotatingFileHandler 实现日志轮转）
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
        """配置 structlog（使用标准库集成模式）"""
        structlog.configure(
            processors=[
                # 过滤日志级别
                structlog.stdlib.filter_by_level,
                # 添加 logger 名称
                structlog.stdlib.add_logger_name,
                # 添加日志级别
                structlog.stdlib.add_log_level,
                # 位置信息处理器
                structlog.stdlib.PositionalArgumentsFormatter(),
                # 时间戳
                structlog.processors.TimeStamper(fmt="iso"),
                # 堆栈信息
                structlog.processors.StackInfoRenderer(),
                # 异常信息
                structlog.processors.UnicodeDecoder(),
                # 最终处理：传递给标准库
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

    @classmethod
    def _get_shared_processors(cls) -> list:
        """
        获取共享的 structlog 处理器列表（用于处理非 structlog 的日志）

        Returns:
            list: structlog 处理器列表
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
        """
        获取指定名称的结构化日志记录器（线程安全）

        Args:
            name: 日志记录器名称，通常使用模块名或类名

        Returns:
            FilteringBoundLogger: 配置好的 structlog 日志记录器实例
        """
        # 如果日志系统还未初始化，先初始化
        if not cls._initialized:
            cls.setup_logging()

        logger_name = name or "root"

        # 使用锁保护 logger 字典的访问
        with cls._setup_lock:
            if logger_name not in cls._loggers:
                logger = structlog.get_logger(logger_name)
                cls._loggers[logger_name] = logger

            return cls._loggers[logger_name]

    @classmethod
    def get_log_file_path(cls) -> str | None:
        """
        获取当前会话的日志文件路径

        Returns:
            Optional[str]: 日志文件路径，如果未初始化则返回 None
        """
        return cls._log_file_path

    @classmethod
    def reset(cls) -> None:
        """
        重置日志系统（主要用于测试，线程安全）
        """
        with cls._setup_lock:
            cls._loggers.clear()
            cls._log_file_path = None
            cls._session_start_time = None
            cls._initialized = False
            cls._log_level = None
            cls._debug = False

            # 清除根日志记录器的处理器
            root_logger = logging.getLogger()
            root_logger.handlers.clear()

            # 重置 structlog 配置
            structlog.reset_defaults()


# 便捷函数：设置日志系统
def setup_logging(log_level: str | None = None) -> None:
    """
    设置日志系统的便捷函数

    Args:
        log_level: 日志级别
    """
    StructLogger.setup_logging(log_level)


# 便捷函数：获取日志记录器
def get_logger(name: str | None = None) -> "FilteringBoundLogger":
    """
    获取结构化日志记录器的便捷函数

    Args:
        name: 日志记录器名称

    Returns:
        FilteringBoundLogger: 配置好的 structlog 日志记录器实例
    """
    return StructLogger.get_logger(name)


def log_execution_time(name: str | None = None, level: str = "info", log_args: bool = False):
    """
    可配置的方法执行时间记录装饰器
    :param name: 方法名称
    :param level: 日志级别 (info/debug/warn/error)
    :param log_args: 是否记录方法入参
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
                # 可选：记录方法入参
                if log_args:
                    log_kwargs["args"] = args
                    log_kwargs["kwargs"] = kwargs

                # 根据指定级别记录日志
                getattr(logger, level)("method_execution_complete", **log_kwargs)

        return wrapper

    return decorator
