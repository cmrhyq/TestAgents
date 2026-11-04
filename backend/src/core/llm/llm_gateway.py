"""LLM 整合层门面。

业务代码只经本模块调用 LLM，统一转发到 ``LLMService`` 并落 llm_log 统计。
``get_model`` 与 ``astream_events`` 绕过埋点，仅限调试或高级用法。
"""

from collections.abc import AsyncIterator, Iterator
from typing import Any, Literal, cast
import warnings

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
    "astream_with_tools",
    "get_model",
]


# 消息格式转换（dict ↔ BaseMessage）

def convert_to_langchain_messages(messages: list[dict[str, str]]) -> list[BaseMessage]:
    """把 dict 消息列表转换为 LangChain 消息对象。

    ``role`` 缺省按 ``user`` 处理，无法识别时同样按用户消息处理。

    Args:
        messages: 形如 ``[{"role": "system/user/assistant", "content": "..."}]``

    Returns:
        LangChain 消息列表，顺序与入参一致
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


# LLMGateway 门面

class LLMGateway:
    """LLM 门面。

    对上保持 dict 消息进、纯文本或流式增量出的接口形态；
    对下所有调用都经 ``LLMService``，自动落 llm_log 统计。

    Args:
        service: 底层服务实例；None 时使用全局单例
    """

    def __init__(self, service: LLMService | None = None) -> None:
        self._service = service or get_llm_service()

    @property
    def service(self) -> LLMService:
        """返回底层 ``LLMService`` 实例。"""
        return self._service

    # 基础调用：dict 消息转纯文本

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """发送聊天请求并返回纯文本响应。

        Args:
            messages: dict 形式的消息列表
            **kwargs: 透传给底层 ``BaseChatModel.invoke``

        Returns:
            模型响应的纯文本
        """
        logger.debug(f"LLM调用开始，消息数: {len(messages)}", message_count=len(messages))
        response = self._service.invoke(convert_to_langchain_messages(messages), **kwargs)
        content = _normalize_message_content(response.content)
        logger.debug(f"LLM调用完成，响应长度: {len(content)}", response_length=len(content))
        return content

    async def achat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """异步发送聊天请求并返回纯文本响应。

        Args:
            messages: dict 形式的消息列表
            **kwargs: 透传给底层 ``ainvoke``

        Returns:
            模型响应的纯文本
        """
        logger.debug(f"LLM异步调用开始，消息数: {len(messages)}", message_count=len(messages))
        response = await self._service.ainvoke(convert_to_langchain_messages(messages), **kwargs)
        content = _normalize_message_content(response.content)
        logger.debug(f"LLM异步调用完成，响应长度: {len(content)}", response_length=len(content))
        return content

    # 流式接口：文本增量

    def chat_stream(self, messages: list[dict[str, str]], **kwargs: Any) -> Iterator[str]:
        """流式发送聊天请求，逐个产出文本增量。

        Args:
            messages: dict 形式的消息列表
            **kwargs: 透传给底层 ``stream``

        Yields:
            非空文本片段，按模型产出顺序
        """
        logger.debug(f"LLM流式调用开始，消息数: {len(messages)}", message_count=len(messages))
        total_length = 0
        for chunk in self._service.stream(convert_to_langchain_messages(messages), **kwargs):
            text = _extract_chunk_text(chunk)
            if text:
                total_length += len(text)
                yield text
        logger.debug(f"LLM流式调用完成，累计响应长度: {total_length}", response_length=total_length)

    async def achat_stream(self, messages: list[dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
        """异步流式发送聊天请求，逐个产出文本增量。

        Args:
            messages: dict 形式的消息列表
            **kwargs: 透传给底层 ``astream``

        Yields:
            非空文本片段，按模型产出顺序
        """
        logger.debug(f"LLM异步流式调用开始，消息数: {len(messages)}", message_count=len(messages))
        total_length = 0
        async for chunk in self._service.astream(convert_to_langchain_messages(messages), **kwargs):
            text = _extract_chunk_text(chunk)
            if text:
                total_length += len(text)
                yield text
        logger.debug(f"LLM异步流式调用完成，累计响应长度: {total_length}", response_length=total_length)

    # 工具调用：返回含 tool_calls 的 AIMessage

    def invoke_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[Any],
        **kwargs: Any,
    ) -> AIMessage:
        """绑定工具后发送请求，返回模型响应。

        Args:
            messages: LangChain 消息列表
            tools: 工具列表，支持 LangChain ``@tool`` 或 OpenAI 格式 dict
            **kwargs: 透传给底层 ``invoke_with_tools``

        Returns:
            含 ``tool_calls`` / ``content`` / ``usage_metadata`` 的响应
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
        """异步绑定工具后发送请求，返回模型响应。

        Args:
            messages: LangChain 消息列表
            tools: 工具列表
            **kwargs: 透传给底层 ``ainvoke_with_tools``

        Returns:
            含 ``tool_calls`` 的响应
        """
        response = await self._service.ainvoke_with_tools(messages, tools, **kwargs)
        logger.debug(
            f"AInvoke With Tools 调用完成，使用工具: {tools}",
            tool_calls=response.tool_calls,
        )
        return response

    # 工具调用（流式）：带统计埋点的入口

    async def astream_with_tools(
        self,
        messages: list[BaseMessage] | list[dict[str, str]],
        tools: list[Any],
        *,
        space_id: int | str | None = None,
        conversation_id: int | None = None,
        run_id: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[BaseMessage]:
        """绑定工具后流式产出 chunk，并记录 llm_log。

        Agent 运行时必须走本入口；自行 ``bind_tools().astream()`` 不会产生统计。

        Args:
            messages: LangChain 消息列表，也接受 dict 形式并在内部转换
            tools: 工具列表；空列表时不绑定
            space_id: 归因空间
            conversation_id: 归因会话
            run_id: 归因执行记录 ``agent_run.id``
            **kwargs: 透传给底层 ``astream_with_tools``

        Yields:
            模型输出的 ``AIMessageChunk``
        """
        langchain_messages = self._as_messages(messages)
        async for chunk in self._service.astream_with_tools(
            langchain_messages,
            tools,
            space_id=space_id,
            conversation_id=conversation_id,
            run_id=run_id,
            **kwargs,
        ):
            yield chunk

    @staticmethod
    def _as_messages(messages: list[BaseMessage] | list[dict[str, str]]) -> list[BaseMessage]:
        """按首元素类型判断入参形态，必要时转换为 LangChain 消息。"""
        if messages and isinstance(messages[0], BaseMessage):
            return list(messages)  # type: ignore[arg-type]
        return convert_to_langchain_messages(messages)  # type: ignore[arg-type]

    # 底层模型透出（高级用法）

    def get_model(self) -> BaseChatModel:
        """返回底层聊天模型。

        已弃用：调用不经过 llm_log 埋点，不会被统计。
        业务代码应改用 ``invoke_with_tools`` / ``astream_with_tools``。

        Returns:
            底层 ``BaseChatModel`` 实例
        """
        warnings.warn(
            "get_model() 绕过 llm_log 统计；请改用 astream_with_tools() / invoke_with_tools()",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._service.model

    async def astream_events(
        self,
        messages: list[dict[str, str]] | list[BaseMessage],
        version: Literal["v1", "v2"] = "v2",
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """异步流式产出 LangChain 细粒度事件。

        直接透传底层模型的 ``astream_events``，不经过 llm_log 埋点。

        Args:
            messages: 消息列表，支持 dict 与 LangChain 消息混用
            version: 事件协议版本
            **kwargs: 透传给底层 ``astream_events``

        Yields:
            事件字典
        """
        if messages and isinstance(messages[0], BaseMessage):
            langchain_messages = messages
        else:
            langchain_messages = convert_to_langchain_messages(messages)  # type: ignore[arg-type]
        async for event in self._service.model.astream_events(langchain_messages, version=version, **kwargs):
            yield cast(dict[str, Any], cast(object, event))

    # 观测

    def get_model_names(self) -> list[str]:
        """返回 Router 中配置的全部模型名。"""
        return self._service.get_model_names()

    @property
    def default_model(self) -> str:
        """返回当前默认模型名。"""
        return self._service.default_model


# 模块级便捷函数

def chat(messages: list[dict[str, str]], **kwargs: Any) -> str:
    """发送聊天请求并返回纯文本，等价于 ``get_llm_gateway().chat``。

    Args:
        messages: dict 形式的消息列表
        **kwargs: 透传给底层 ``invoke``

    Returns:
        模型响应的纯文本
    """
    return get_llm_gateway().chat(messages, **kwargs)


def chat_stream(messages: list[dict[str, str]], **kwargs: Any) -> Iterator[str]:
    """同步流式产出文本增量。

    Yields:
        非空文本片段
    """
    return get_llm_gateway().chat_stream(messages, **kwargs)


def achat_stream(messages: list[dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
    """异步流式产出文本增量。

    Yields:
        非空文本片段
    """
    return get_llm_gateway().achat_stream(messages, **kwargs)


def invoke_with_tools(messages: list[BaseMessage], tools: list[Any], **kwargs: Any) -> AIMessage:
    """绑定工具发送请求并返回模型响应。

    Returns:
        含 ``tool_calls`` 的响应
    """
    return get_llm_gateway().invoke_with_tools(messages, tools, **kwargs)


def astream_with_tools(
    messages: list[BaseMessage] | list[dict[str, str]],
    tools: list[Any],
    **kwargs: Any,
) -> AsyncIterator[BaseMessage]:
    """流式工具调用，带 llm_log 统计。

    Yields:
        模型输出的 chunk
    """
    return get_llm_gateway().astream_with_tools(messages, tools, **kwargs)


def get_model() -> BaseChatModel:
    """返回底层聊天模型；已弃用，调用不产生统计。"""
    return get_llm_gateway().get_model()


# 全局单例

_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    """返回全局门面单例，首次调用时创建。

    Returns:
        全局唯一的 ``LLMGateway``
    """
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway(get_llm_service())
    return _gateway


def init_llm_gateway() -> LLMGateway:
    """重置服务层后重建全局门面。

    副作用：丢弃现有 ``LLMService`` 与网关实例。

    Returns:
        新建的门面实例
    """
    global _gateway
    reset_llm_service()
    _gateway = LLMGateway(get_llm_service())
    return _gateway


def reset_llm_gateway() -> None:
    """清除全局门面实例，仅供测试使用。"""
    global _gateway
    _gateway = None
