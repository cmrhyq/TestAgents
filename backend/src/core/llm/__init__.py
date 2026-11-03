"""LLM 整合层模块。

业务代码只经 ``llm_gateway`` 调用 LLM：门面提供 dict 消息 / 纯文本 / 流式 token 三种入口，
向下由 ``llm_service`` 封装 LiteLLM Router 并统一落 llm_log 统计。
"""

from src.core.llm.llm_gateway import (
    LLMGateway,
    achat_stream,
    chat,
    chat_stream,
    get_llm_gateway,
    get_model,
    init_llm_gateway,
    invoke_with_tools,
)
from src.core.llm.llm_service import (
    LLMService,
    get_llm_service,
    reset_llm_service,
)

__all__ = [
    "LLMGateway",
    "achat_stream",
    "chat",
    "chat_stream",
    "get_llm_gateway",
    "get_model",
    "init_llm_gateway",
    "invoke_with_tools",
    "LLMService",
    "get_llm_service",
    "reset_llm_service",
]
