"""配置管理模块。

应用配置只从 YAML 文件加载，文件缺失或解析失败时回退到 ``AppConfig`` 的字段默认值。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def get_backend_root() -> Path:
    """返回 backend 根目录。

    工作目录、内置 skill 目录等相对路径配置均以此为基准解析，不依赖进程 cwd。
    """
    return Path(__file__).resolve().parent.parent.parent


def resolve_backend_path(raw: str | Path) -> Path:
    """把配置里的路径解析为绝对路径：相对路径以 backend 根为基准。"""
    path = Path(raw)
    return path if path.is_absolute() else (get_backend_root() / path)


class LLMConfig(BaseModel):
    """LLM 配置。"""

    default_model: str = Field(default="smart-router", description="默认模型名（对应 model_list 中的 model_name，smart-router=复杂度自动路由）")


class DatabaseConfig(BaseModel):
    """数据库配置。"""

    url: str = Field(default="sqlite:///db/TestAgents.db", description="数据库连接URL")
    echo: bool = Field(default=False, description="是否输出SQL语句")
    pool_size: int = Field(default=5, description="连接池大小")
    max_overflow: int = Field(default=10, description="最大溢出连接数")
    pool_timeout: int = Field(default=30, description="连接池获取超时（秒）")
    pool_recycle: int = Field(default=3600, description="连接回收时间（秒）")


class ChromaConfig(BaseModel):
    """ChromaDB 向量数据库配置。"""

    enabled: bool = Field(default=False, description="是否启用 ChromaDB（关闭时知识库降级为词法检索）")
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


class EmbeddingConfig(BaseModel):
    """向量化模型配置。

    未启用或调用失败时，知识库检索降级为 SQLite 词法匹配，不向上抛错。
    """

    enabled: bool = Field(default=False, description="是否启用向量化（关闭时知识库走词法检索）")
    model: str = Field(default="", description="litellm 格式的 embedding 模型名，如 zai/embedding-3")
    api_key: str = Field(default="", description="API 密钥")
    base_url: str = Field(default="", description="自定义服务端点")
    dimension: int = Field(default=1024, description="向量维度（用于建集合时的校验）")


class WorkspaceConfig(BaseModel):
    """空间工作目录配置。"""

    root: str = Field(default="workspaces", description="工作目录根（相对 backend 或绝对路径）")
    max_file_size_kb: int = Field(default=256, description="Agent 单次读取文件的大小上限（KB）")
    tree_max_depth: int = Field(default=3, description="目录树接口默认深度")
    tree_max_entries: int = Field(default=500, description="目录树单层条目上限，防爆量")


class SkillConfig(BaseModel):
    """Skill 配置。"""

    builtin_root: str = Field(default="skills", description="内置 skill 目录（相对 backend 或绝对路径）")
    max_skill_chars: int = Field(default=8000, description="单个 skill 注入 system prompt 的正文上限")


class ModelPricing(BaseModel):
    """自定义模型费率（美元 / token）。

    用于 litellm 定价表未收录的厂商模型，未配置时该模型调用成本记为 NULL。
    必须与 ``model_list`` 分开配置：混入 ``litellm_params`` 会被当作未知 provider 参数透传。
    """

    model: str = Field(..., description="模型名，与 model_list 里的 litellm_params.model 一致")
    input_cost_per_token: float = Field(default=0.0, description="输入 token 单价（美元）")
    output_cost_per_token: float = Field(default=0.0, description="输出 token 单价（美元）")


class LoggingConfig(BaseModel):
    """日志配置。"""

    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="console", description="输出格式: console(彩色) / json(生产环境)")
    debug: bool = Field(default=False, deprecated="debug参数已废弃，请使用format字段", description="调试模式(已废弃)")


class AppConfig(BaseModel):
    """应用配置。"""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    chroma: ChromaConfig = Field(default_factory=ChromaConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    skill: SkillConfig = Field(default_factory=SkillConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    pricing: list[ModelPricing] = Field(
        default_factory=list,
        description="自定义模型费率，用于 litellm 定价表未收录的模型（影响 llm_log.cost_usd）",
    )
    model_list: list[dict[str, Any]] = Field(
        default_factory=list,
        description="LiteLLM Router 模型列表（model_name + litellm_params），透传给 litellm.Router",
    )


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """加载应用配置。

    文件缺失或解析失败时记录告警，回退到字段默认值。

    Args:
        config_path: 配置文件路径；None 时取 ``config/config.yaml``

    Returns:
        应用配置对象
    """
    if config_path is None:
        resolved_path = get_backend_root() / "config" / "config.yaml"
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


_config: AppConfig | None = None


def get_config() -> AppConfig:
    """返回全局配置实例；首次调用时从默认路径加载并缓存。

    Returns:
        应用配置对象
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def init_config(config_path: str | None = None) -> AppConfig:
    """加载配置并覆盖全局实例。

    Args:
        config_path: 配置文件路径；None 时使用默认路径

    Returns:
        应用配置对象
    """
    global _config
    _config = load_config(config_path)
    return _config
