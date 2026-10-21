"""LLM 整合层模块。

分层结构（项目调用 LLM 的唯一入口是 llm_gateway）::

    业务代码 → llm_gateway（门面）→ llm_service（Router + llm_log 统计）

- ``llm_gateway``：对上提供便捷接口（dict 消息 / 纯文本 / 流式 token）
- ``llm_service``：对下封装 LiteLLM Router，所有调用自动落 llm_log 统计
- ``llm_client``：已废弃，仅保留待清理
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
    # 整合层（推荐业务代码使用）
    "LLMGateway",
    "achat_stream",
    "chat",
    "chat_stream",
    "get_llm_gateway",
    "get_model",
    "init_llm_gateway",
    "invoke_with_tools",
    # 服务层
    "LLMService",
    "get_llm_service",
    "reset_llm_service",
]
