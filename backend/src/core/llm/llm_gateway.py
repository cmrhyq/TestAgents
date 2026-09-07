"""LLM 整合层（门面）。

整个项目调用 LLM 的**唯一入口**：业务代码只 import 本模块，
由 gateway 统一转发到 ``LLMService``（含 llm_log 统计落库）。

分层::

    业务代码（nodes / skill / api）
        └── llm_gateway（本模块：消息格式适配 + 能力门面）
                └── llm_service（LLMService：Router + llm_log 埋点）

提供的适配能力（均为 llm_client 时代的旧接口形态）：
- ``chat(messages: list[dict]) -> str``：dict 消息 → 纯文本响应
- ``chat_stream / achat_stream``：dict 消息 → 文本增量（token）
- ``invoke_with_tools``：BaseMessage → AIMessage（.tool_calls）
- ``get_model()``：返回底层 BaseChatModel（供 bind_tools 等高级用法）

用法::

    from src.core.llm.llm_gateway import get_llm_gateway, chat

    # 1) 便捷函数（推荐，最简单）
    answer = chat([{"role": "user", "content": "帮我测试登录接口"}])

    # 2) 网关实例
    gw = get_llm_gateway()
    answer = gw.chat(messages)
    for token in gw.chat_stream(messages):
        print(token, end="")

    # 3) 工具调用（LangGraph ToolNode 模式）
    response = gw.invoke_with_tools(messages, tools=[search_space])
    print(response.tool_calls)

    # 4) 需要 BaseChatModel 的场景（如 bind_tools + 自行 invoke）
    model = gw.get_model()
"""

from collections.abc import AsyncIterator, Iterator
from typing import Any, Literal, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.core.llm.llm_service import (
    LLMService,
    get_llm_service,
    reset_llm_service,
)
from src.core.logging import get_logger

logger = get_logger(__name__)

__all__ = [
    "LLMGateway",
    "get_llm_gateway",
    "init_llm_gateway",
    "reset_llm_gateway",
    "chat",
    "chat_stream",
    "achat_stream",
    "invoke_with_tools",
    "get_model",
]


# ---------------------------------------------------------------------------
# 消息格式转换（dict ↔ BaseMessage）
# ---------------------------------------------------------------------------

def convert_to_langchain_messages(messages: list[dict[str, str]]) -> list[BaseMessage]:
    """将字典格式消息列表转换为 LangChain BaseMessage 列表。

    Args:
        messages: [{"role": "system/user/assistant", "content": "..."}]

    Returns:
        LangChain 消息列表
    """
    result: list[BaseMessage] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "assistant":
            result.append(AIMessage(content=content))
        else:
            result.append(HumanMessage(content=content))
    return result


def _normalize_message_content(content: str | list) -> str:
    """将 LangChain 消息的 content 归一化为纯文本字符串。"""
    if isinstance(content, list):
        return "".join(part if isinstance(part, str) else str(part) for part in content)
    return content or ""


def _extract_chunk_text(chunk: BaseMessage) -> str:
    """从流式响应 chunk 中提取纯文本增量。"""
    return _normalize_message_content(getattr(chunk, "content", "") or "")


# ---------------------------------------------------------------------------
# LLMGateway：统一门面
# ---------------------------------------------------------------------------

class LLMGateway:
    """LLM 整合层门面。

    对上（业务代码）：保持 llm_client 时代的便捷接口
    （dict 消息进 / 纯文本出 / 流式文本增量）。
    对下（LLMService）：全部调用走 LLMService，
    自动获得 llm_log 统计落库能力。

    Args:
        service: LLMService 实例，为 None 时使用全局单例。
    """

    def __init__(self, service: LLMService | None = None) -> None:
        self._service = service or get_llm_service()

    @property
    def service(self) -> LLMService:
        """底层 LLMService 实例。"""
        return self._service

    # ------------------------------------------------------------------
    # 基础调用：dict 消息 → 纯文本
    # ------------------------------------------------------------------

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """发送聊天请求，返回纯文本响应。

        Args:
            messages: [{"role": "system/user/assistant", "content": "..."}]
            **kwargs: 透传给底层 BaseChatModel.invoke

        Returns:
            模型响应的纯文本
        """
        logger.debug(f"LLM调用开始，消息数: {len(messages)}", message_count=len(messages))
        response = self._service.invoke(convert_to_langchain_messages(messages), **kwargs)
        content = _normalize_message_content(response.content)
        logger.debug(f"LLM调用完成，响应长度: {len(content)}", response_length=len(content))
        return content

    async def achat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """异步发送聊天请求，返回纯文本响应。"""
        logger.debug(f"LLM异步调用开始，消息数: {len(messages)}", message_count=len(messages))
        response = await self._service.ainvoke(convert_to_langchain_messages(messages), **kwargs)
        content = _normalize_message_content(response.content)
        logger.debug(f"LLM异步调用完成，响应长度: {len(content)}", response_length=len(content))
        return content

    # ------------------------------------------------------------------
    # 流式接口：文本增量（str）
    # ------------------------------------------------------------------

    def chat_stream(self, messages: list[dict[str, str]], **kwargs: Any) -> Iterator[str]:
        """流式发送聊天请求，逐个产出文本增量（token）。"""
        logger.debug(f"LLM流式调用开始，消息数: {len(messages)}", message_count=len(messages))
        total_length = 0
        for chunk in self._service.stream(convert_to_langchain_messages(messages), **kwargs):
            text = _extract_chunk_text(chunk)
            if text:
                total_length += len(text)
                yield text
        logger.debug(f"LLM流式调用完成，累计响应长度: {total_length}", response_length=total_length)

    async def achat_stream(self, messages: list[dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
        """异步流式发送聊天请求，逐个产出文本增量（token）。"""
        logger.debug(f"LLM异步流式调用开始，消息数: {len(messages)}", message_count=len(messages))
        total_length = 0
        async for chunk in self._service.astream(convert_to_langchain_messages(messages), **kwargs):
            text = _extract_chunk_text(chunk)
            if text:
                total_length += len(text)
                yield text
        logger.debug(f"LLM异步流式调用完成，累计响应长度: {total_length}", response_length=total_length)

    # ------------------------------------------------------------------
    # 工具调用：BaseMessage → AIMessage（含 .tool_calls）
    # ------------------------------------------------------------------

    def invoke_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[Any],
        **kwargs: Any,
    ) -> AIMessage:
        """使用 LangChain 消息发送带工具绑定的请求，返回 AIMessage。

        Args:
            messages: LangChain BaseMessage 列表
            tools: 工具列表（LangChain @tool 或 OpenAI 格式 dict）
            **kwargs: 透传给底层 invoke

        Returns:
            AIMessage（含 .tool_calls / .content / .usage_metadata）
        """
        response = self._service.invoke_with_tools(messages, tools, **kwargs)
        logger.debug(
            f"Invoke With Tools 调用完成，使用工具: {tools}",
            tool_calls=response.tool_calls,
        )
        return response

    async def ainvoke_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[Any],
        **kwargs: Any,
    ) -> AIMessage:
        """异步发送带工具绑定的请求，返回 AIMessage。"""
        response = await self._service.ainvoke_with_tools(messages, tools, **kwargs)
        logger.debug(
            f"AInvoke With Tools 调用完成，使用工具: {tools}",
            tool_calls=response.tool_calls,
        )
        return response

    # ------------------------------------------------------------------
    # 底层模型透出（bind_tools / astream_events 等高级用法）
    # ------------------------------------------------------------------

    def get_model(self) -> BaseChatModel:
        """返回底层 BaseChatModel（ChatLiteLLMRouter）。

        供需要直接操作模型的场景使用（如 LangGraph ToolNode 的
        ``model.bind_tools(tools).invoke(...)`` 循环、astream_events）。
        注意：直接操作 model 不经过 llm_log 统计埋点。
        """
        return self._service.model

    async def astream_events(
        self,
        messages: list[dict[str, str]] | list[BaseMessage],
        version: Literal["v1", "v2"] = "v2",
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """异步流式产出细粒度事件（on_chat_model_stream 等）。

        注意：直接透传底层 model 的 astream_events，不经过 llm_log 埋点。
        """
        if messages and isinstance(messages[0], BaseMessage):
            langchain_messages = messages
        else:
            langchain_messages = convert_to_langchain_messages(messages)  # type: ignore[arg-type]
        async for event in self._service.model.astream_events(langchain_messages, version=version, **kwargs):
            yield cast(dict[str, Any], cast(object, event))

    # ------------------------------------------------------------------
    # 观测透出
    # ------------------------------------------------------------------

    def get_model_names(self) -> list[str]:
        """返回 Router 中配置的全部模型名。"""
        return self._service.get_model_names()

    @property
    def default_model(self) -> str:
        """当前默认模型名。"""
        return self._service.default_model


# ---------------------------------------------------------------------------
# 模块级便捷函数（最常用路径的一行调用）
# ---------------------------------------------------------------------------

def chat(messages: list[dict[str, str]], **kwargs: Any) -> str:
    """模块级便捷函数：等同于 ``get_llm_gateway().chat(messages)``。"""
    return get_llm_gateway().chat(messages, **kwargs)


def chat_stream(messages: list[dict[str, str]], **kwargs: Any) -> Iterator[str]:
    """模块级便捷函数：流式文本增量。"""
    return get_llm_gateway().chat_stream(messages, **kwargs)


def achat_stream(messages: list[dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
    """模块级便捷函数：异步流式文本增量。"""
    return get_llm_gateway().achat_stream(messages, **kwargs)


def invoke_with_tools(messages: list[BaseMessage], tools: list[Any], **kwargs: Any) -> AIMessage:
    """模块级便捷函数：带工具调用。"""
    return get_llm_gateway().invoke_with_tools(messages, tools, **kwargs)


def get_model() -> BaseChatModel:
    """模块级便捷函数：获取底层 BaseChatModel。"""
    return get_llm_gateway().get_model()


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    """获取全局 LLMGateway 单例。"""
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway(get_llm_service())
    return _gateway


def init_llm_gateway() -> LLMGateway:
    """重新初始化全局网关（应用启动/热重载时调用）。"""
    global _gateway
    reset_llm_service()
    _gateway = LLMGateway(get_llm_service())
    return _gateway


def reset_llm_gateway() -> None:
    """重置全局单例（测试用）。"""
    global _gateway
    _gateway = None
