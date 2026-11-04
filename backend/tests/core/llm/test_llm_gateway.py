"""`LLMGateway` 的调用入口与消息归一化。

覆盖 `chat` / `achat`、两条流式入口、`invoke_with_tools`、`astream_events`
与消息转换 helper；全部用 MagicMock 替换 `LLMService`，不发起真实请求。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage

from src.core.llm.llm_gateway import (
    LLMGateway,
    _extract_chunk_text,
    _normalize_message_content,
    convert_to_langchain_messages,
)


def _gateway_with_service() -> tuple[LLMGateway, MagicMock]:
    """构造注入了 mock service 的网关。"""
    service = MagicMock()
    return LLMGateway(service=service), service


class TestMessageHelpers:
    """消息归一化 helper。"""

    def test_convert_dict_messages(self):
        messages = convert_to_langchain_messages(
            [
                {"role": "system", "content": "s"},
                {"role": "assistant", "content": "a"},
                {"role": "user", "content": "u"},
            ]
        )
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], AIMessage)
        assert isinstance(messages[2], HumanMessage)

    def test_normalize_plain_string(self):
        assert _normalize_message_content("abc") == "abc"

    def test_normalize_none_returns_empty(self):
        assert _normalize_message_content(None) == ""

    def test_normalize_list_content(self):
        assert _normalize_message_content(["a", "b"]) == "ab"

    def test_extract_chunk_text(self):
        assert _extract_chunk_text(AIMessageChunk(content="tok")) == "tok"

    def test_extract_chunk_without_content(self):
        assert _extract_chunk_text(MagicMock(spec=[])) == ""


class TestChat:
    """`chat` 与 `achat` 的文本归一化。"""

    def test_chat_returns_normalized_text(self):
        gateway, service = _gateway_with_service()
        service.invoke.return_value = AIMessage(content="hello")

        assert gateway.chat([{"role": "user", "content": "hi"}]) == "hello"
        # dict 需先转换为 BaseMessage 再交给 service
        passed = service.invoke.call_args.args[0]
        assert isinstance(passed[0], HumanMessage)

    @pytest.mark.asyncio
    async def test_achat_returns_normalized_text(self):
        gateway, service = _gateway_with_service()
        service.ainvoke = AsyncMock(return_value=AIMessage(content="async hello"))

        assert await gateway.achat([{"role": "user", "content": "hi"}]) == "async hello"


class TestStream:
    """两条流式入口只产出非空分片。"""

    def test_chat_stream_yields_only_non_empty(self):
        gateway, service = _gateway_with_service()
        service.stream.return_value = iter(
            [AIMessageChunk(content="a"), AIMessageChunk(content=""), AIMessageChunk(content="b")]
        )

        assert list(gateway.chat_stream([{"role": "user", "content": "hi"}])) == ["a", "b"]

    @pytest.mark.asyncio
    async def test_achat_stream_yields_only_non_empty(self):
        gateway, service = _gateway_with_service()

        async def _gen():
            yield AIMessageChunk(content="x")
            yield AIMessageChunk(content="")
            yield AIMessageChunk(content="y")

        service.astream = MagicMock(return_value=_gen())

        chunks = [c async for c in gateway.achat_stream([{"role": "user", "content": "hi"}])]
        assert chunks == ["x", "y"]


class TestTools:
    """`invoke_with_tools` 的参数透传。"""

    def test_invoke_with_tools_passthrough(self):
        gateway, service = _gateway_with_service()
        service.invoke_with_tools.return_value = AIMessage(
            content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]
        )
        messages: list[BaseMessage] = [HumanMessage(content="hi")]

        response = gateway.invoke_with_tools(messages, tools=["tool-a"])

        assert response.tool_calls[0]["name"] == "t"
        service.invoke_with_tools.assert_called_once_with(messages, ["tool-a"])


class TestAstreamEvents:
    """`astream_events` 先把 dict 消息转成 `BaseMessage`。"""

    @pytest.mark.asyncio
    async def test_dict_messages_are_converted(self):
        gateway, service = _gateway_with_service()
        captured: dict = {}

        async def _events(messages, version="v2", **kwargs):
            captured["messages"] = messages
            yield {"event": "on_chat_model_stream", "data": {}}

        service.model = MagicMock()
        service.model.astream_events = _events

        events = [e async for e in gateway.astream_events([{"role": "user", "content": "hi"}])]

        assert events[0]["event"] == "on_chat_model_stream"
        assert isinstance(captured["messages"][0], HumanMessage)


class TestObservability:
    """模型名与默认模型透出。"""

    def test_get_model_names(self):
        gateway, service = _gateway_with_service()
        service.get_model_names.return_value = ["m1", "m2"]

        assert gateway.get_model_names() == ["m1", "m2"]

    def test_default_model(self):
        gateway, service = _gateway_with_service()
        service.default_model = "m1"

        assert gateway.default_model == "m1"
