"""
配置管理模块

负责加载和管理应用配置，仅从 YAML 文件读取配置。
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LLMConfig(BaseModel):
    """LLM配置"""

    default_model: str = Field(default="smart-router", description="默认模型名（对应 model_list 中的 model_name，smart-router=复杂度自动路由）")


class RetryConfig(BaseModel):
    """重试配置"""

    max_retries: int = Field(default=2, description="最大重试次数")
    retry_interval: float = Field(default=1.0, description="重试间隔（秒）")
    retry_on_status: list[int] = Field(default=[500, 502, 503, 504], description="需要重试的状态码")


class ConcurrencyConfig(BaseModel):
    """并发配置"""

    enabled: bool = Field(default=True, description="是否启用并发")
    max_workers: int = Field(default=5, description="最大并发数")


class ExecutionConfig(BaseModel):
    """测试执行配置"""

    connect_timeout: int = Field(default=5, description="连接超时（秒）")
    read_timeout: int = Field(default=30, description="读取超时（秒）")
    total_timeout: int = Field(default=60, description="总超时（秒）")
    retry: RetryConfig = Field(default_factory=RetryConfig)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    dependency_failure: str = Field(default="skip", description="依赖失败处理方式")


class OutputConfig(BaseModel):
    """输出配置"""

    base_dir: str = Field(default="output", description="输出根目录")
    test_cases_dir: str = Field(default="", description="用例目录（留空则动态生成时间戳子目录）")
    reports_dir: str = Field(default="", description="报告目录（留空则动态生成时间戳子目录）")

    def get_test_cases_dir(self) -> str:
        """获取用例目录（动态生成时间戳）"""
        if self.test_cases_dir:
            return self.test_cases_dir
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{self.base_dir}/{ts}/test_cases"

    def get_reports_dir(self) -> str:
        """获取报告目录（动态生成时间戳）"""
        if self.reports_dir:
            return self.reports_dir
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{self.base_dir}/{ts}/reports"


class DatabaseConfig(BaseModel):
    """数据库配置"""

    url: str = Field(default="sqlite:///db/TestAgents.db", description="数据库连接URL")
    echo: bool = Field(default=False, description="是否输出SQL语句")
    pool_size: int = Field(default=5, description="连接池大小")
    max_overflow: int = Field(default=10, description="最大溢出连接数")
    pool_timeout: int = Field(default=30, description="连接池获取超时（秒）")
    pool_recycle: int = Field(default=3600, description="连接回收时间（秒）")


class ChromaConfig(BaseModel):
    """ChromaDB 向量数据库配置"""

    host: str = Field(default="localhost", description="ChromaDB 服务地址")
    port: int = Field(default=8000, description="ChromaDB 服务端口")
    auth_provider: str = Field(
        default="chromadb.auth.token_authn.TokenAuthClientProvider",
        description="认证提供者类路径",
    )
    auth_credentials: str = Field(default="", description="认证凭证（Token）")
    auth_token_transport_header: str = Field(
        default="Authorization",
        description="Token 传输 Header（Authorization 或 X-Chroma-Token）",
    )
    tenant: str = Field(default="default_tenant", description="租户名称")
    database: str = Field(default="default_database", description="数据库名称")
    default_collection: str = Field(default="default", description="默认集合名称")


class LoggingConfig(BaseModel):
    """日志配置"""

    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="console", description="输出格式: console(彩色) / json(生产环境)")
    debug: bool = Field(default=False, deprecated="debug参数已废弃，请使用format字段", description="调试模式(已废弃)")


class LangSmithConfig(BaseModel):
    """LangSmith 可观测性配置"""

    enabled: bool = Field(default=False, description="是否启用 LangSmith 追踪")
    api_key: str = Field(default="", description="LangSmith API 密钥")
    space: str = Field(default="TestAgents", description="LangSmith 空间名称")
    endpoint: str = Field(default="https://api.smith.langchain.com", description="LangSmith 服务端点")


class AppConfig(BaseModel):
    """应用配置"""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    chroma: ChromaConfig = Field(default_factory=ChromaConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    langsmith: LangSmithConfig = Field(default_factory=LangSmithConfig)
    model_list: list[dict[str, Any]] = Field(
        default_factory=list,
        description="LiteLLM Router 模型列表（model_name + litellm_params），透传给 litellm.Router",
    )


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """
    加载应用配置

    Args:
        config_path: 配置文件路径，默认为 config/config.yaml

    Returns:
        AppConfig: 应用配置对象
    """
    if config_path is None:
        space_root = Path(__file__).parent.parent.parent
        resolved_path = space_root / "config" / "config.yaml"
    else:
        resolved_path = Path(config_path)

    config_data: dict[str, Any] = {}

    if resolved_path.exists():
        try:
            with open(resolved_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
            logger.info("配置文件加载成功: %s", resolved_path)
        except Exception as e:
            logger.warning(f"配置文件加载失败，使用默认配置, error: {e}", exc_info=e)
    else:
        logger.warning("配置文件不存在: %s，使用默认配置", resolved_path)

    return AppConfig(**config_data)


def ensure_output_dirs(config: AppConfig) -> None:
    """
    确保输出目录存在

    Args:
        config: 应用配置
    """
    dirs = [
        config.output.base_dir,
        config.output.get_test_cases_dir(),
        config.output.get_reports_dir(),
    ]

    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.debug("输出目录已确认: %s", dir_path)


def _setup_langsmith(config: AppConfig) -> None:
    """
    根据配置启用或禁用 LangSmith 追踪。

    LangChain/LangGraph 通过检测环境变量自动决定是否上报追踪数据，
    此函数在应用启动时统一设置相关环境变量。

    Args:
        config: 应用配置
    """
    if config.langsmith.enabled and config.langsmith.api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = config.langsmith.api_key
        os.environ["LANGSMITH_SPACE"] = config.langsmith.space
        if config.langsmith.endpoint:
            os.environ["LANGSMITH_ENDPOINT"] = config.langsmith.endpoint
        logger.info("LangSmith 追踪已启用, space=%s", config.langsmith.space)
    else:
        os.environ.pop("LANGSMITH_TRACING", None)
        os.environ.pop("LANGSMITH_API_KEY", None)
        os.environ.pop("LANGSMITH_SPACE", None)
        os.environ.pop("LANGSMITH_ENDPOINT", None)
        logger.info("LangSmith 追踪未启用")


# 全局配置实例
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """
    获取全局配置实例

    Returns:
        AppConfig: 应用配置对象
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def init_config(config_path: str | None = None) -> AppConfig:
    """
    初始化配置

    Args:
        config_path: 配置文件路径

    Returns:
        AppConfig: 应用配置对象
    """
    global _config
    _config = load_config(config_path)
    ensure_output_dirs(_config)
    _setup_langsmith(_config)
    return _config
