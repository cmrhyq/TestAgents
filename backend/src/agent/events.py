"""SSE 事件协议。

前端只认这六种事件，名字与载荷形状即契约。改名字等于改 API 版本。

    start        流开始，带会话/空间/模式/技能上下文
    text_delta   模型输出的文本增量
    tool_call    工具调用开始（含参数，前端可折叠展示）
    tool_result  工具返回（含耗时与成败，长内容会截断）
    final        最终回答（完整文本，避免前端拼接误差）
    error        链路错误

一个刻意的设计：``final`` 里带完整 answer，而不是让前端把 ``text_delta``
拼起来。拼接会因为丢帧/重连产生错位，而答案必须准确。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, ClassVar

# 单个工具结果下发的字符上限。工具结果可能很大（响应体、文件内容），
# 全量推给前端既没必要也会拖垮渲染
MAX_TOOL_RESULT_CHARS = 4_000


@dataclass(slots=True)
class StartEvent:
    conversation_id: int | None
    space_id: int | None
    mode: str
    skills: list[str] = field(default_factory=list)

    EVENT_NAME: ClassVar[str] = "start"

    def payload(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "space_id": self.space_id,
            "mode": self.mode,
            "skills": self.skills,
        }


@dataclass(slots=True)
class TextDeltaEvent:
    content: str

    EVENT_NAME: ClassVar[str] = "text_delta"

    def payload(self) -> dict[str, Any]:
        return {"content": self.content}


@dataclass(slots=True)
class ToolCallEvent:
    id: str
    name: str
    args: dict[str, Any]

    EVENT_NAME: ClassVar[str] = "tool_call"

    def payload(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "args": self.args}


@dataclass(slots=True)
class ToolResultEvent:
    id: str
    name: str
    ok: bool
    content: str
    duration_ms: int
    EVENT_NAME: ClassVar[str] = "tool_result"

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "ok": self.ok,
            "content": _truncate(self.content),
            "duration_ms": self.duration_ms,
        }


@dataclass(slots=True)
class FinalEvent:
    answer: str
    usage: dict[str, Any] = field(default_factory=dict)

    EVENT_NAME: ClassVar[str] = "final"

    def payload(self) -> dict[str, Any]:
        return {"answer": self.answer, "usage": self.usage}


@dataclass(slots=True)
class ErrorEvent:
    message: str

    EVENT_NAME: ClassVar[str] = "error"

    def payload(self) -> dict[str, Any]:
        return {"message": self.message}


AgentEvent = StartEvent | TextDeltaEvent | ToolCallEvent | ToolResultEvent | FinalEvent | ErrorEvent


def render(event: AgentEvent, seq: int) -> str:
    """把事件渲染为 SSE 帧。

    帧格式固定三行 + 空行：``id`` 支撑断线续传，``event`` 供前端按类型分发，
    ``data`` 承载载荷。``default=str`` 兜住不可 JSON 化的值，避免一帧失败打断整条流。
    """
    payload = {"seq": seq, "type": event.EVENT_NAME, "ts": None, **event.payload()}
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"id: {seq}\nevent: {event.EVENT_NAME}\ndata: {data}\n\n"


def _truncate(content: str) -> str:
    if len(content) <= MAX_TOOL_RESULT_CHARS:
        return content
    return content[:MAX_TOOL_RESULT_CHARS] + f"\n…（已截断，原始长度 {len(content)} 字符）"
