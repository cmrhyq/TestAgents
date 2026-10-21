"""SSE 事件协议测试。

协议是前后端的契约，形状一旦定下就不能随意改。这里锁定三件事：
帧格式（id/event/data 三行）、事件名、以及 tool_result 的截断行为。
"""

import json

from src.agent.events import (
    ErrorEvent,
    FinalEvent,
    StartEvent,
    TextDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
    render,
)


def _parse(frame: str) -> tuple[int, str, dict]:
    """把 SSE 帧拆回 (seq, event_name, payload)。"""
    lines = frame.strip().split("\n")
    seq = int(lines[0].removeprefix("id: "))
    name = lines[1].removeprefix("event: ")
    payload = json.loads(lines[2].removeprefix("data: "))
    return seq, name, payload


class TestFrameFormat:
    def test_three_line_frame_with_blank_line(self):
        frame = render(TextDeltaEvent(content="hi"), seq=3)

        assert frame.endswith("\n\n")
        assert frame.startswith("id: 3\nevent: text_delta\ndata: ")

    def test_non_ascii_preserved(self):
        frame = render(TextDeltaEvent(content="中文内容"), seq=0)
        _, _, payload = _parse(frame)

        assert payload["content"] == "中文内容"
        assert "中文内容" in frame  # ensure_ascii=False


class TestEvents:
    def test_start_carries_context(self):
        event = StartEvent(conversation_id=1, space_id=2, mode="agent", skills=["a"])
        seq, name, payload = _parse(render(event, 0))

        assert name == "start"
        assert payload["conversation_id"] == 1
        assert payload["space_id"] == 2
        assert payload["mode"] == "agent"
        assert payload["skills"] == ["a"]
        assert payload["seq"] == seq

    def test_text_delta(self):
        _, name, payload = _parse(render(TextDeltaEvent(content="abc"), 1))
        assert name == "text_delta"
        assert payload["content"] == "abc"

    def test_tool_call(self):
        event = ToolCallEvent(id="call-1", name="read_file", args={"path": "a.md"})
        _, name, payload = _parse(render(event, 2))

        assert name == "tool_call"
        assert payload["id"] == "call-1"
        assert payload["name"] == "read_file"
        assert payload["args"] == {"path": "a.md"}

    def test_tool_result_truncates_long_content(self):
        event = ToolResultEvent(id="c1", name="read_file", ok=True, content="x" * 10_000, duration_ms=12)
        _, name, payload = _parse(render(event, 3))

        assert name == "tool_result"
        assert len(payload["content"]) < 5_000
        assert "截断" in payload["content"]
        assert payload["ok"] is True
        assert payload["duration_ms"] == 12

    def test_tool_result_short_content_intact(self):
        event = ToolResultEvent(id="c1", name="t", ok=False, content="error", duration_ms=1)
        _, _, payload = _parse(render(event, 0))
        assert payload["content"] == "error"

    def test_final(self):
        event = FinalEvent(answer="完成", usage={"total_tokens": 100})
        _, name, payload = _parse(render(event, 9))

        assert name == "final"
        assert payload["answer"] == "完成"
        assert payload["usage"] == {"total_tokens": 100}

    def test_error(self):
        _, name, payload = _parse(render(ErrorEvent(message="boom"), 4))
        assert name == "error"
        assert payload["message"] == "boom"


class TestEventNames:
    def test_names_are_stable(self):
        """事件名是前端分发依据，改动等于破坏契约。"""
        assert StartEvent(1, 2, "agent", []).EVENT_NAME == "start"
        assert TextDeltaEvent("x").EVENT_NAME == "text_delta"
        assert ToolCallEvent("i", "n", {}).EVENT_NAME == "tool_call"
        assert ToolResultEvent("i", "n", True, "", 0).EVENT_NAME == "tool_result"
        assert FinalEvent("a").EVENT_NAME == "final"
        assert ErrorEvent("m").EVENT_NAME == "error"
