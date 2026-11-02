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
from src.agent.recording import NullRecorder
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


async def _fake_run(_request, *, recorder=None):
    """预置事件序列：工具调用一次，再给最终回答。"""
    yield StartEvent(conversation_id=7, space_id=1, mode="agent", skills=["s"])
    yield ToolCallEvent(id="c1", name="get_space_endpoints", args={"space_id": 1})
    yield ToolResultEvent(id="c1", name="get_space_endpoints", ok=True, content="[]", duration_ms=3)
    yield TextDeltaEvent(content="空间 1 ")
    yield TextDeltaEvent(content="共有 0 个接口。")
    yield FinalEvent(answer="空间 1 共有 0 个接口。")


async def _failing_run(_request, *, recorder=None):
    yield StartEvent(conversation_id=7, space_id=1, mode="agent", skills=[])
    yield ErrorEvent(message="模型调用失败：网关超时")


class _SpyRecorder:
    """记录调用过程的假记录器，供终态断言使用。"""

    run_id: int | None = None

    def __init__(self) -> None:
        self.started: dict | None = None
        self.finished: dict | None = None
        self.tool_calls: list[dict] = []

    def start(self, **kwargs) -> int | None:
        self.started = kwargs
        self.run_id = 9001
        return 9001

    def tool_call(self, **kwargs) -> None:
        self.tool_calls.append(kwargs)

    def finish(self, *, status: str, error_message: str = "") -> None:
        self.finished = {"status": status, "error_message": error_message}


def _spy_factory() -> tuple[_SpyRecorder, type]:
    """构造「同一个实例」的记录器类，便于测试拿到实例断言。"""
    spy = _SpyRecorder()

    class _Factory(_SpyRecorder):
        def __new__(cls, *args, **kwargs):
            return spy

    return spy, _Factory


def _make_body(**overrides):
    from types import SimpleNamespace as NS

    payload = {
        "instruction": "空间 1 有哪些接口",
        "space_id": 1,
        "conversation_id": 7,
        "mode": "agent",
        "skill_names": [],
        "environment_id": None,
    }
    payload.update(overrides)
    return NS(**payload)


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(chat_router, prefix="/api/v1")
    return TestClient(app)


@contextmanager
def patched(*, runner=_fake_run, prepare=None, conversation_id: int = 7, recorder_cls=NullRecorder):
    """替换外部依赖：会话落库、上下文装配、回答落库、runner、执行记录器。

    执行记录器换成 ``NullRecorder``：这组测试聚焦 SSE 协议，不该因为
    测试环境没有数据库而反复打印「记录创建失败」并让断言依赖 DB。
    """
    prepare = prepare or (lambda body, cid: RunRequest(instruction="问", space_id=1, mode="agent"))
    with (
        patch.object(ChatStreamService, "ensure_conversation", return_value=conversation_id),
        patch.object(ChatStreamService, "prepare", side_effect=prepare),
        patch.object(ChatStreamService, "save_answer") as save,
        patch("src.data.services.chat_stream_service.run_agent", side_effect=runner),
        patch("src.data.services.chat_stream_service.AgentRunRecorder", recorder_cls),
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


# ---------------------------------------------------------------------------
# 执行记录生命周期
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRunRecorderLifecycle:
    """终态判定是本轮改造的核心：``finally`` 必须把三种收尾都写对。

    最要紧的是**断流**：客户端关标签页时 Starlette 对生成器调 ``aclose()``，
    挂起点抛 ``GeneratorExit``。如果 ``finally`` 里 ``await``（写库）就会被
    ``CancelledError`` 打断，记录永久卡在 ``running``——清理任务还不敢碰它。
    """

    async def test_start_is_called_with_request_context(self):
        spy, factory = _spy_factory()

        with patched(recorder_cls=factory):
            async for _ in ChatStreamService().stream_answer(_make_body(), 7):
                pass

        assert spy.started is not None
        assert spy.started["space_id"] == 1
        assert spy.started["conversation_id"] == 7
        assert spy.started["mode"] == "agent"
        assert spy.started["title"] == "空间 1 有哪些接口"

    async def test_run_id_is_backfilled_into_request(self):
        seen: dict = {}

        async def _capture(request, *, recorder=None):
            seen["run_id"] = request.run_id
            seen["recorder"] = recorder
            yield StartEvent(conversation_id=7, space_id=1, mode="agent", skills=[])
            yield FinalEvent(answer="好")

        spy, factory = _spy_factory()
        with patched(runner=_capture, recorder_cls=factory):
            async for _ in ChatStreamService().stream_answer(_make_body(), 7):
                pass

        # run_id 必须回填，否则 runner 里的工具埋点与 llm_log 的 run_id 会全是空
        assert seen["run_id"] == 9001
        assert seen["recorder"] is spy

    async def test_completed_status_and_answer_persisted(self):
        spy, factory = _spy_factory()

        with patched(recorder_cls=factory) as mocks:
            async for _ in ChatStreamService().stream_answer(_make_body(), 7):
                pass

        assert spy.finished == {"status": "completed", "error_message": ""}
        mocks.save.assert_called_once_with(7, "空间 1 共有 0 个接口。")

    async def test_error_event_marks_failed_and_skips_persist(self):
        spy, factory = _spy_factory()

        with patched(runner=_failing_run, recorder_cls=factory) as mocks:
            async for _ in ChatStreamService().stream_answer(_make_body(), 7):
                pass

        assert spy.finished["status"] == "failed"
        assert "网关超时" in spy.finished["error_message"]
        mocks.save.assert_not_called()

    async def test_generator_aclose_marks_cancelled(self):
        """模拟客户端断连：取到第一帧就 aclose，终态必须是 cancelled。"""
        spy, factory = _spy_factory()

        with patched(recorder_cls=factory) as mocks:
            gen = ChatStreamService().stream_answer(_make_body(), 7)
            first = await gen.__anext__()
            assert "event: start" in first
            await gen.aclose()

        assert spy.finished == {"status": "cancelled", "error_message": ""}
        # 半截回答不能落库：断流时 answer 还没拼完
        mocks.save.assert_not_called()

    async def test_prepare_failure_creates_no_record(self):
        """上下文装配就失败时不该留下任何记录——那时 finally 还没建立。"""
        spy, factory = _spy_factory()

        def boom(_body, _cid):
            raise RuntimeError("db down")

        with patched(prepare=boom, recorder_cls=factory):
            async for _ in ChatStreamService().stream_answer(_make_body(), 7):
                pass

        assert spy.started is None
        assert spy.finished is None
