"""/api/v1/chat/stream 流式接口测试。

关注三件事：

1. **SSE 帧契约**：三行帧、seq 从 0 连续、事件类型顺序
2. **模式兼容**：agent / ask / plan 及历史值都能出流（模式决定工具集在 runner 层已测）
3. **降级**：上下文装配失败、模型报错都要变成 ``error`` 帧，而不是 5xx

上下文装配与 runner 全部 mock，测试只验证协议与编排。
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agent.runner import RunRequest
from src.agent.events import (
    ErrorEvent,
    FinalEvent,
    StartEvent,
    TextDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from src.api.v1.chat import router as chat_router
from src.data.services.chat_stream_service import ChatStreamService

# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _parse_frames(body: str) -> list[dict]:
    """把 SSE 响应体解析为 data 载荷列表。"""
    payloads: list[dict] = []
    for block in body.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                payloads.append(json.loads(line[5:].strip()))
    return payloads


def _frame_ids(body: str) -> list[int]:
    """提取所有 id: 行的序号。"""
    return [int(line.split(":", 1)[1].strip()) for line in body.split("\n") if line.startswith("id:")]


async def _fake_run(_request):
    """预置事件序列：工具调用一次，再给最终回答。"""
    yield StartEvent(conversation_id=7, space_id=1, mode="agent", skills=["s"])
    yield ToolCallEvent(id="c1", name="get_space_endpoints", args={"space_id": 1})
    yield ToolResultEvent(id="c1", name="get_space_endpoints", ok=True, content="[]", duration_ms=3)
    yield TextDeltaEvent(content="空间 1 ")
    yield TextDeltaEvent(content="共有 0 个接口。")
    yield FinalEvent(answer="空间 1 共有 0 个接口。")


async def _failing_run(_request):
    yield StartEvent(conversation_id=7, space_id=1, mode="agent", skills=[])
    yield ErrorEvent(message="模型调用失败：网关超时")


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(chat_router, prefix="/api/v1")
    return TestClient(app)


@contextmanager
def patched(*, runner=_fake_run, prepare=None, conversation_id: int = 7):
    """替换外部依赖：会话落库、上下文装配、回答落库、runner。"""
    prepare = prepare or (lambda body, cid: RunRequest(instruction="问", space_id=1, mode="agent"))
    with (
        patch.object(ChatStreamService, "ensure_conversation", return_value=conversation_id),
        patch.object(ChatStreamService, "prepare", side_effect=prepare),
        patch.object(ChatStreamService, "save_answer") as save,
        patch("src.data.services.chat_stream_service.run_agent", side_effect=runner),
    ):
        yield SimpleNamespace(save=save)


# ---------------------------------------------------------------------------
# 协议契约
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStreamProtocol:
    def test_headers(self, client):
        with patched():
            response = client.post(
                "/api/v1/chat/stream",
                json={"instruction": "空间 1 有哪些接口", "space_id": 1},
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-conversation-id"] == "7"
        # 网关不设这条会把整条流攒完再吐，流式失去意义
        assert response.headers["x-accel-buffering"] == "no"

    def test_event_types_and_sequence(self, client):
        with patched():
            response = client.post(
                "/api/v1/chat/stream",
                json={"instruction": "接口清单", "space_id": 1},
            )

        payloads = _parse_frames(response.text)
        assert [p["type"] for p in payloads] == [
            "start",
            "tool_call",
            "tool_result",
            "text_delta",
            "text_delta",
            "final",
        ]
        assert [p["seq"] for p in payloads] == [0, 1, 2, 3, 4, 5]
        assert _frame_ids(response.text) == [0, 1, 2, 3, 4, 5]

    def test_three_line_frame_shape(self, client):
        with patched():
            response = client.post(
                "/api/v1/chat/stream", json={"instruction": "问", "space_id": 1}
            )

        first = response.text.split("\n\n")[0].split("\n")
        assert len(first) == 3
        assert first[0].startswith("id: ")
        assert first[1].startswith("event: ")
        assert first[2].startswith("data: ")

    def test_tool_payloads_carry_args_and_ok(self, client):
        with patched():
            response = client.post(
                "/api/v1/chat/stream",
                json={"instruction": "接口清单", "space_id": 1},
            )

        payloads = _parse_frames(response.text)
        assert payloads[1]["name"] == "get_space_endpoints"
        assert payloads[1]["args"] == {"space_id": 1}
        assert payloads[2]["ok"] is True
        assert payloads[5]["answer"] == "空间 1 共有 0 个接口。"

    def test_final_answer_is_persisted(self, client):
        with patched() as mocks:
            client.post("/api/v1/chat/stream", json={"instruction": "问", "space_id": 1})

        mocks.save.assert_called_once_with(7, "空间 1 共有 0 个接口。")

    def test_error_stream_does_not_persist(self, client):
        """失败的轮次不落库——半截回答会比没有回答更误导。"""
        with patched(runner=_failing_run) as mocks:
            response = client.post("/api/v1/chat/stream", json={"instruction": "问", "space_id": 1})

        assert _parse_frames(response.text)[-1]["type"] == "error"
        mocks.save.assert_not_called()


# ---------------------------------------------------------------------------
# 前置校验与降级
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPreconditions:
    def test_missing_space_yields_error_frame(self, client):
        with patch.object(ChatStreamService, "ensure_conversation", return_value=7):
            response = client.post("/api/v1/chat/stream", json={"instruction": "问"})

        payloads = _parse_frames(response.text)
        assert response.status_code == 200
        assert payloads[-1]["type"] == "error"
        assert "测试空间" in payloads[-1]["message"]

    def test_empty_instruction_rejected(self, client):
        with patch.object(ChatStreamService, "ensure_conversation", return_value=7):
            response = client.post("/api/v1/chat/stream", json={"instruction": "", "space_id": 1})

        assert response.status_code == 422

    def test_prepare_failure_becomes_error_frame(self, client):
        def boom(_body, _cid):
            raise RuntimeError("db down")

        with patched(prepare=boom):
            response = client.post("/api/v1/chat/stream", json={"instruction": "问", "space_id": 1})

        payloads = _parse_frames(response.text)
        assert response.status_code == 200
        assert payloads[-1]["type"] == "error"
        assert "db down" in payloads[-1]["message"]

    def test_request_fields_are_forwarded_to_prepare(self, client):
        seen: dict = {}

        def capture(body, _cid):
            seen["body"] = body
            return RunRequest(instruction="问", space_id=1, mode="agent")

        with patched(prepare=capture):
            client.post(
                "/api/v1/chat/stream",
                json={
                    "instruction": "问",
                    "space_id": 1,
                    "mode": "plan",
                    "skill_names": ["api-test-design"],
                    "environment_id": 3,
                },
            )

        body = seen["body"]
        assert body.skill_names == ["api-test-design"]
        assert body.environment_id == 3
        assert body.mode == "plan"

    @pytest.mark.parametrize("mode", ["agent", "ask", "plan", "Run", "Ask", "Plan", ""])
    def test_all_modes_are_accepted(self, client, mode):
        with patched():
            response = client.post(
                "/api/v1/chat/stream",
                json={"instruction": "问", "space_id": 1, "mode": mode},
            )

        assert response.status_code == 200
        assert _parse_frames(response.text)[0]["type"] == "start"
