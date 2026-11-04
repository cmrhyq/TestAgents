"""Runner 与 LLM 统计的接线契约。

未注入模型时必须走 `astream_with_tools` 并透传归因字段，不得调用 `get_model`：
后者绕过 `LLMService` 埋点，会使对话链路不产生任何 `llm_log`。
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessageChunk

from src.agent.events import FinalEvent, StartEvent
from src.agent.runner import RunRequest, run

SPACE_ID = 9101
CONVERSATION_ID = 9201


class RecordingGateway:
    """记录调用参数的假网关，`get_model` 一旦被调用即失败。"""

    def __init__(self, rounds: list[list[AIMessageChunk]]) -> None:
        self._rounds = rounds
        self.calls: list[dict[str, Any]] = []
        self.tools_per_call: list[set[str]] = []

    def get_model(self):  # pragma: no cover - 被调用即测试失败
        raise AssertionError("runner 不应调用 get_model：它会绕过 llm_log 埋点")

    async def astream_with_tools(self, messages, tools, **kwargs):
        self.calls.append({"messages": list(messages), "tools": list(tools), **kwargs})
        self.tools_per_call.append({t.name for t in tools})
        index = min(len(self.calls) - 1, len(self._rounds) - 1)
        for chunk in self._rounds[index]:
            yield chunk


def _request() -> RunRequest:
    """构造 ask 模式的请求。"""
    return RunRequest(
        instruction="空间里有哪些接口",
        space_id=SPACE_ID,
        conversation_id=CONVERSATION_ID,
        mode="ask",
    )


async def _collect(events) -> list:
    """把异步事件流收成列表。"""
    return [event async for event in events]


@pytest.fixture()
def patched_gateway(monkeypatch):
    """返回装填函数，把全局 gateway 替换为记录器。"""

    def _install(rounds: list[list[AIMessageChunk]]) -> RecordingGateway:
        gateway = RecordingGateway(rounds)
        monkeypatch.setattr("src.core.llm.llm_gateway.get_llm_gateway", lambda: gateway)
        return gateway

    return _install


class TestStatelessPath:
    """默认路径（无注入模型）必须走带埋点的入口。"""

    async def test_uses_astream_with_tools(self, patched_gateway):
        gateway = patched_gateway([[AIMessageChunk(content="没有接口")]])

        await _collect(run(_request()))

        assert len(gateway.calls) == 1

    async def test_passes_attribution(self, patched_gateway):
        gateway = patched_gateway([[AIMessageChunk(content="ok")]])

        await _collect(run(_request()))

        call = gateway.calls[0]
        assert call["space_id"] == SPACE_ID
        assert call["conversation_id"] == CONVERSATION_ID

    async def test_does_not_touch_get_model(self, patched_gateway):
        """`get_model` 被调用即抛错，用例随之失败。"""
        patched_gateway([[AIMessageChunk(content="ok")]])

        events = await _collect(run(_request()))

        assert isinstance(events[0], StartEvent)
        assert isinstance(events[-1], FinalEvent)

    async def test_passes_filtered_tools(self, patched_gateway):
        """ask 模式仍按白名单裁剪工具，更换入口不改变该行为。"""
        gateway = patched_gateway([[AIMessageChunk(content="ok")]])

        await _collect(run(_request()))

        names = gateway.tools_per_call[0]
        assert "send_request" not in names
        assert "write_file" not in names
        assert "read_file" in names

    async def test_each_round_goes_through_gateway(self, patched_gateway):
        """工具轮次每轮都是一次计费调用，需各走一次网关。"""
        gateway = patched_gateway(
            [
                [
                    AIMessageChunk(
                        content="",
                        tool_call_chunks=[
                            {"name": "read_file", "args": '{"path": "AGENTS.md"}', "id": "c1", "index": 0}
                        ],
                    )
                ],
                [AIMessageChunk(content="读完了")],
            ]
        )

        events = await _collect(run(_request()))

        assert len(gateway.calls) == 2
        assert isinstance(events[-1], FinalEvent)
        assert events[-1].answer == "读完了"


class TestInjectedModel:
    """注入模型（单测路径）不应触碰全局网关。"""

    async def test_injected_model_bypasses_gateway(self, patched_gateway):
        from langchain_core.tools import BaseTool

        class FakeModel:
            def bind_tools(self, tools: list[BaseTool]):
                return self

            async def astream(self, messages):
                yield AIMessageChunk(content="注入模型回答")

        # 全局 gateway 装成一碰即错，用于验证注入路径确实绕开它
        patched_gateway([[]])

        events = await _collect(run(_request(), model=FakeModel()))

        assert isinstance(events[-1], FinalEvent)
        assert events[-1].answer == "注入模型回答"
