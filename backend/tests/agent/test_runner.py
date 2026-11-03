"""Agent 运行时的 ReAct 循环：事件序列、工具执行与失败兜底。

约束：`start` 为首帧，`final` / `error` 为末帧；工具异常转为 `ok=False` 结果而非中断流；
超出步数上限必须显式报错。用例全部由假模型驱动，不发起网络请求。
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage
from langchain_core.tools import BaseTool, tool

from src.agent.events import (
    ErrorEvent,
    FinalEvent,
    StartEvent,
    TextDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from src.agent.modes import policy_for
from src.agent.runner import RunRequest, run
from src.agent.tools.registry import ToolBundle


# ---------------------------------------------------------------------------
# 假模型：按剧本逐轮流式吐出 chunk
# ---------------------------------------------------------------------------

class FakeModel:
    """按剧本回放的假模型。

    `script` 为轮次列表，跑完后重复最后一轮，超步数用例无需写出完整剧本。
    """

    def __init__(self, script: list[list[AIMessageChunk]]) -> None:
        self.script = script
        self.round = 0
        self.bound_tools: list[BaseTool] = []
        self.seen_messages: list[list[Any]] = []
        self.fail_with: Exception | None = None

    def bind_tools(self, tools: list[BaseTool]) -> "FakeModel":
        self.bound_tools = list(tools)
        return self

    async def astream(self, messages: list[Any]):
        self.seen_messages.append(list(messages))
        if self.fail_with is not None:
            raise self.fail_with
        index = min(self.round, len(self.script) - 1)
        self.round += 1
        for chunk in self.script[index]:
            yield chunk


def text_turn(*parts: str) -> list[AIMessageChunk]:
    """一轮纯文本输出。"""
    return [AIMessageChunk(content=part) for part in parts]


def tool_turn(
    calls: list[tuple[str, dict]], *, text: str = "", prefix: str = "call"
) -> list[AIMessageChunk]:
    """一轮带工具调用的输出，`calls` 为 `(工具名, 参数)` 列表。

    参数拆成两段发送，用于覆盖流式分片合并。
    """
    chunks: list[AIMessageChunk] = []
    if text:
        chunks.append(AIMessageChunk(content=text))
    for index, (name, args) in enumerate(calls):
        payload = json.dumps(args, ensure_ascii=False)
        half = max(1, len(payload) // 2)
        chunks.append(
            AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {"name": name, "args": payload[:half], "id": f"{prefix}-{index}", "index": index}
                ],
            )
        )
        chunks.append(
            AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {"name": None, "args": payload[half:], "id": None, "index": index}
                ],
            )
        )
    return chunks


# ---------------------------------------------------------------------------
# 假工具
# ---------------------------------------------------------------------------

@tool
def echo(value: str) -> str:
    """原样回显传入的值。"""
    return f"echo:{value}"


@tool
def boom(value: str) -> str:
    """总是抛异常。"""
    raise RuntimeError("工具内部炸了")


@tool
def accumulate(value: str) -> str:
    """记录每次调用。"""
    _CALLS.append(value)
    return f"ok:{value}"


@tool
def write_file(path: str) -> str:
    """写文件，用于验证模式裁剪。"""
    return f"wrote:{path}"


_CALLS: list[str] = []


def make_bundle(mode: str = "agent") -> ToolBundle:
    """构造含回显、异常与累加三个假工具的 bundle。"""
    policy = policy_for(mode)
    return ToolBundle(tools=[echo, boom, accumulate], policy=policy)


def make_request(**overrides: Any) -> RunRequest:
    """构造带默认空间上下文的请求。"""
    base: dict[str, Any] = {
        "instruction": "帮我看看登录接口",
        "space_id": 9001,
        "space_name": "演示空间",
        "mode": "agent",
    }
    base.update(overrides)
    return RunRequest(**base)


async def collect(model: FakeModel, request: RunRequest | None = None, **kwargs: Any):
    """收集 `run` 产出的全部事件。"""
    events = []
    async for event in run(request or make_request(), model=model, **kwargs):
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------

class TestPlainText:
    """纯文本回复：事件序列与首轮消息组装。"""

    async def test_emits_start_then_deltas_then_final(self):
        model = FakeModel([text_turn("你好", "，世界")])

        events = await collect(model, bundle=make_bundle())

        assert isinstance(events[0], StartEvent)
        assert [e.content for e in events if isinstance(e, TextDeltaEvent)] == ["你好", "，世界"]
        assert isinstance(events[-1], FinalEvent)
        assert events[-1].answer == "你好，世界"

    async def test_no_tool_events(self):
        events = await collect(FakeModel([text_turn("答")]), bundle=make_bundle())

        assert not any(isinstance(e, (ToolCallEvent, ToolResultEvent)) for e in events)

    async def test_start_carries_request_context(self):
        request = make_request(conversation_id=42, mode="plan", skill_names=["s1"])

        events = await collect(FakeModel([text_turn("x")]), request=request, bundle=make_bundle("plan"))

        start = events[0]
        assert isinstance(start, StartEvent)
        assert start.conversation_id == 42
        assert start.space_id == 9001
        assert start.mode == "plan"
        assert start.skills == ["s1"]

    async def test_model_only_called_once(self):
        model = FakeModel([text_turn("一次")])
        await collect(model, bundle=make_bundle())

        assert model.round == 1

    async def test_system_prompt_and_instruction_are_sent(self):
        model = FakeModel([text_turn("x")])

        await collect(model, request=make_request(instruction="查登录"), bundle=make_bundle())

        sent = model.seen_messages[0]
        assert sent[0].type == "system"
        assert "执行模式" in sent[0].content
        assert sent[-1].type == "human"
        assert sent[-1].content == "查登录"


class TestSingleTool:
    """单轮工具调用：事件配对与结果回灌。"""

    async def test_emits_call_and_result(self):
        model = FakeModel([tool_turn([("echo", {"value": "hi"})]), text_turn("好了")])

        events = await collect(model, bundle=make_bundle())

        call = next(e for e in events if isinstance(e, ToolCallEvent))
        assert call.name == "echo"
        assert call.args == {"value": "hi"}
        assert call.id == "call-0"

        result = next(e for e in events if isinstance(e, ToolResultEvent))
        assert result.ok is True
        assert result.content == "echo:hi"
        assert result.id == call.id
        assert result.duration_ms >= 0

    async def test_result_is_fed_back_as_tool_message(self):
        model = FakeModel([tool_turn([("echo", {"value": "hi"})]), text_turn("好了")])

        await collect(model, bundle=make_bundle())

        second_round = model.seen_messages[1]
        tool_messages = [m for m in second_round if isinstance(m, ToolMessage)]
        assert len(tool_messages) == 1
        assert tool_messages[0].content == "echo:hi"
        assert tool_messages[0].tool_call_id == "call-0"

    async def test_assistant_tool_call_is_recorded(self):
        """模型本轮的 tool_calls 必须回写进 messages，否则下一轮上下文缺环。"""
        model = FakeModel([tool_turn([("echo", {"value": "hi"})]), text_turn("好了")])

        await collect(model, bundle=make_bundle())

        ai = [m for m in model.seen_messages[1] if m.type == "ai"]
        assert ai and ai[-1].tool_calls[0]["name"] == "echo"

    async def test_partial_json_args_are_merged(self):
        """分片传参需拼成完整 dict，否则工具会收到空参数。"""
        model = FakeModel(
            [tool_turn([("echo", {"value": "一段比较长的值用来触发分片"})]), text_turn("ok")]
        )

        events = await collect(model, bundle=make_bundle())

        call = next(e for e in events if isinstance(e, ToolCallEvent))
        assert call.args == {"value": "一段比较长的值用来触发分片"}

    async def test_final_answer_after_tool(self):
        model = FakeModel([tool_turn([("echo", {"value": "a"})]), text_turn("最终", "答案")])

        events = await collect(model, bundle=make_bundle())

        assert isinstance(events[-1], FinalEvent)
        assert events[-1].answer == "最终答案"

    async def test_text_before_tool_call_is_streamed(self):
        model = FakeModel([tool_turn([("echo", {"value": "a"})], text="我先查一下"), text_turn("ok")])

        events = await collect(model, bundle=make_bundle())

        deltas = [e.content for e in events if isinstance(e, TextDeltaEvent)]
        assert deltas[0] == "我先查一下"


class TestMultiRound:
    """多轮与单轮并行工具调用。"""

    async def test_two_rounds_of_tools(self):
        _CALLS.clear()
        model = FakeModel(
            [
                tool_turn([("accumulate", {"value": "1"})]),
                tool_turn([("accumulate", {"value": "2"})]),
                text_turn("都做完了"),
            ]
        )

        events = await collect(model, bundle=make_bundle())

        assert _CALLS == ["1", "2"]
        assert len([e for e in events if isinstance(e, ToolResultEvent)]) == 2
        assert isinstance(events[-1], FinalEvent)

    async def test_parallel_calls_in_one_round(self):
        _CALLS.clear()
        model = FakeModel(
            [tool_turn([("accumulate", {"value": "a"}), ("accumulate", {"value": "b"})]), text_turn("ok")]
        )

        events = await collect(model, bundle=make_bundle())

        results = [e for e in events if isinstance(e, ToolResultEvent)]
        assert len(results) == 2
        assert _CALLS == ["a", "b"]
        assert {r.id for r in results} == {"call-0", "call-1"}

    async def test_history_is_prepended(self):
        from langchain_core.messages import HumanMessage

        model = FakeModel([text_turn("x")])
        request = make_request(history=[HumanMessage(content="上一轮的提问")])

        await collect(model, request=request, bundle=make_bundle())

        sent = model.seen_messages[0]
        assert [m.content for m in sent if m.type == "human"] == ["上一轮的提问", "帮我看看登录接口"]


class TestFailure:
    """失败路径：工具异常、未知工具、模型异常与步数熔断。"""

    async def test_tool_exception_becomes_failed_result(self):
        model = FakeModel([tool_turn([("boom", {"value": "x"})]), text_turn("我换个方式")])

        events = await collect(model, bundle=make_bundle())

        result = next(e for e in events if isinstance(e, ToolResultEvent))
        assert result.ok is False
        assert "工具内部炸了" in result.content
        # 异常不得终止流程，模型需要拿到错误信息继续
        assert isinstance(events[-1], FinalEvent)

    async def test_unknown_tool_name_is_reported(self):
        model = FakeModel([tool_turn([("not_exists", {"a": 1})]), text_turn("ok")])

        events = await collect(model, bundle=make_bundle())

        result = next(e for e in events if isinstance(e, ToolResultEvent))
        assert result.ok is False
        assert "not_exists" in result.content

    async def test_model_exception_yields_error_event(self):
        model = FakeModel([text_turn("x")])
        model.fail_with = RuntimeError("网关超时")

        events = await collect(model, bundle=make_bundle())

        assert isinstance(events[-1], ErrorEvent)
        assert "网关超时" in events[-1].message

    async def test_exceeding_max_steps_yields_error(self):
        """模型持续请求工具时必须触发步数熔断。"""
        model = FakeModel([tool_turn([("echo", {"value": "loop"})])])
        bundle = ToolBundle(tools=[echo], policy=policy_for("plan"))  # plan: 8 轮上限

        events = await collect(model, bundle=bundle)

        assert isinstance(events[-1], ErrorEvent)
        assert "轮次" in events[-1].message
        assert model.round == bundle.policy.max_steps

    async def test_cancel_does_not_emit_final(self):
        """消费者提前退出后不应继续调用模型。"""
        model = FakeModel([tool_turn([("echo", {"value": "1"})]), text_turn("ok")])
        stream = run(make_request(), model=model, bundle=make_bundle())

        first = await stream.__anext__()
        assert isinstance(first, StartEvent)
        await stream.aclose()

        assert model.round == 0


class TestEventSequence:
    """全局事件顺序不变式。"""

    async def test_start_is_first_and_single(self):
        model = FakeModel([tool_turn([("echo", {"value": "1"})]), text_turn("ok")])

        events = await collect(model, bundle=make_bundle())

        assert isinstance(events[0], StartEvent)
        assert sum(isinstance(e, StartEvent) for e in events) == 1

    async def test_final_is_last_and_single(self):
        model = FakeModel([tool_turn([("echo", {"value": "1"})]), text_turn("ok")])

        events = await collect(model, bundle=make_bundle())

        assert isinstance(events[-1], FinalEvent)
        assert sum(isinstance(e, FinalEvent) for e in events) == 1

    async def test_call_always_precedes_its_result(self):
        model = FakeModel([tool_turn([("echo", {"value": "1"})]), text_turn("ok")])

        events = await collect(model, bundle=make_bundle())

        call_index = next(i for i, e in enumerate(events) if isinstance(e, ToolCallEvent))
        result_index = next(i for i, e in enumerate(events) if isinstance(e, ToolResultEvent))
        assert call_index < result_index


class TestToolBinding:
    """工具绑定与模式裁剪。"""

    async def test_tools_are_bound_to_model(self):
        model = FakeModel([text_turn("x")])

        await collect(model, bundle=make_bundle())

        assert {t.name for t in model.bound_tools} == {"echo", "boom", "accumulate"}

    async def test_ask_mode_never_sees_side_effect_tools(self):
        """ask 模式下写工具不进入绑定列表，约束落在执行路径而非调用方约定。"""
        bundle = ToolBundle(tools=[echo, write_file], policy=policy_for("ask"))
        model = FakeModel([text_turn("x")])

        await collect(model, bundle=bundle)

        assert "write_file" not in {t.name for t in model.bound_tools}
        assert "echo" in {t.name for t in model.bound_tools}

    async def test_empty_tools_still_runs(self):
        bundle = ToolBundle(tools=[], policy=policy_for("ask"))
        model = FakeModel([text_turn("纯文本回答")])

        events = await collect(model, bundle=bundle)

        assert isinstance(events[-1], FinalEvent)


@pytest.mark.parametrize("mode", ["agent", "ask", "plan"])
async def test_all_modes_produce_final(mode):
    model = FakeModel([text_turn("答")])

    events = await collect(model, request=make_request(mode=mode), bundle=make_bundle(mode))

    assert isinstance(events[-1], FinalEvent)
