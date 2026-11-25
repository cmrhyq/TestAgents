"""LLM 整合层模块。

业务代码只经 ``llm_service`` 调用 LLM；``chat_model`` 负责适配 langchain-litellm，
``llm_service`` 统一落 llm_log 统计。
"""

from src.core.llm.llm_service import (
    LLMService,
    get_llm_service,
    reset_llm_service,
)

__all__ = [
    "LLMService",
    "get_llm_service",
    "reset_llm_service",
]
