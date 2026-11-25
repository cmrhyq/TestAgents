"""SSE 事件协议。

事件名与载荷形状是对前端的契约，共六种：``start`` / ``text_delta`` / ``tool_call`` /
``tool_result`` / ``final`` / ``error``，改名即破坏兼容性。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, ClassVar

from src.data.constant.agent import AGENT_MAX_TOOL_RESULT_CHARS


@dataclass(slots=True)
class StartEvent:
    """流开始事件，携带会话、空间、模式与技能上下文。"""

    conversation_id: int | None
    space_id: int | None
    mode: str
    skills: list[str] = field(default_factory=list)
    # 执行记录 ID，前端据此跳转到本次执行详情。新增字段属于向后兼容的增量。
    run_id: int | None = None

    EVENT_NAME: ClassVar[str] = "start"

    def payload(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "space_id": self.space_id,
            "mode": self.mode,
            "skills": self.skills,
            "run_id": self.run_id,
        }


@dataclass(slots=True)
class TextDeltaEvent:
    """模型输出的文本增量。"""

    content: str

    EVENT_NAME: ClassVar[str] = "text_delta"

    def payload(self) -> dict[str, Any]:
        return {"content": self.content}


@dataclass(slots=True)
class ToolCallEvent:
    """工具调用开始事件，含调用参数。"""

    id: str
    name: str
    args: dict[str, Any]

    EVENT_NAME: ClassVar[str] = "tool_call"

    def payload(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "args": self.args}


@dataclass(slots=True)
class ToolResultEvent:
    """工具返回事件，含成败与耗时，内容按上限截断。"""

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
    """最终回答事件，携带完整文本，前端不自行拼接增量。"""

    answer: str
    usage: dict[str, Any] = field(default_factory=dict)

    EVENT_NAME: ClassVar[str] = "final"

    def payload(self) -> dict[str, Any]:
        return {"answer": self.answer, "usage": self.usage}


@dataclass(slots=True)
class ErrorEvent:
    """链路错误事件。"""

    message: str

    EVENT_NAME: ClassVar[str] = "error"

    def payload(self) -> dict[str, Any]:
        return {"message": self.message}


AgentEvent = StartEvent | TextDeltaEvent | ToolCallEvent | ToolResultEvent | FinalEvent | ErrorEvent


def render(event: AgentEvent, seq: int) -> str:
    """把事件渲染为 SSE 帧。

    帧格式为 ``id`` / ``event`` / ``data`` 三行加空行：``id`` 支撑断线续传。
    ``default=str`` 兜住不可 JSON 化的值，避免单帧失败打断整条流。

    Args:
        event: 待渲染事件
        seq: 帧序号，用于断线续传

    Returns:
        可直接写入流的一个 SSE 帧
    """
    payload = {"seq": seq, "type": event.EVENT_NAME, "ts": None, **event.payload()}
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"id: {seq}\nevent: {event.EVENT_NAME}\ndata: {data}\n\n"


def _truncate(content: str) -> str:
    """截断超长工具结果，并在尾部标注原始长度。"""
    if len(content) <= AGENT_MAX_TOOL_RESULT_CHARS:
        return content
    return content[:AGENT_MAX_TOOL_RESULT_CHARS] + f"\n…（已截断，原始长度 {len(content)} 字符）"
