"""LLM API 自动化测试工具。

基于 LangChain 消息 / 工具抽象与 LiteLLM Router 的大模型 API 自动化测试工具。
"""

__version__ = "1.0.0"
__author__ = "cmrhyq"

from src.core.config import AppConfig, get_config, init_config
from src.core.llm.llm_service import LLMService, get_llm_service

__all__ = [
    "AppConfig",
    "LLMService",
    "get_config",
    "get_llm_service",
    "init_config",
]
