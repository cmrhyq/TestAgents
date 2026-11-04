"""`AgentRunRecorder` 的落库契约。

写入端不得因 DB 异常抛出，异常只记 warning；敏感头入库前脱敏；计数在内存累加，
由 `finish` 一次写出且幂等；成本从 `llm_log` 聚合。
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.agent.recording import ToolOutcome
from src.data.models.base import Base
from src.data.recording.agent_run_recorder import (
    MAX_PREVIEW_CHARS,
    MAX_RESPONSE_BODY_BYTES,
    AgentRunRecorder,
)

SPACE_ID = 7701


@pytest.fixture()
def scope(tmp_path):
    """返回 `(session_scope, maker)`：前者供记录器，后者供断言。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'recorder.db'}")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)

    with maker() as session:
        from src.data.models.space import Space

        session.add(Space(id=SPACE_ID, name="记录空间", workspace_path=f"workspaces/{SPACE_ID}"))
        session.commit()

    @contextmanager
    def _scope():
        session: Session = maker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    yield _scope, maker
    engine.dispose()


def _recorder(scope) -> AgentRunRecorder:
    """基于给定 session 作用域构造记录器。"""
    return AgentRunRecorder(session_scope=scope)


def _run(maker, run_id: int):
    """读取指定执行记录行。"""
    from src.data.models.agent_run import AgentRun

    with maker() as session:
        return session.get(AgentRun, run_id)


def _calls(maker, run_id: int):
    """读取指定执行记录的全部工具调用行。"""
    from src.data.models.agent_tool_call import AgentToolCall

    with maker() as session:
        return list(session.scalars(select(AgentToolCall).where(AgentToolCall.run_id == run_id)))


class TestStart:
    """`start` 建行、字段归一与 DB 不可用时的降级。"""

    def test_creates_running_row(self, scope):
        scope_fn, maker = scope
        recorder = _recorder(scope_fn)

        run_id = recorder.start(space_id=SPACE_ID, conversation_id=7, mode="plan", title="查接口")

        assert run_id is not None
        assert recorder.run_id == run_id
        row = _run(maker, run_id)
        assert row.status == "running"
        assert row.mode == "plan"
        assert row.title == "查接口"
        assert row.conversation_id == 7
        assert row.started_at is not None

    def test_conversation_id_zero_becomes_none(self, scope):
        """`ensure_conversation` 降级返回 0，落库需归一为 None。"""
        scope_fn, maker = scope
        recorder = _recorder(scope_fn)

        run_id = recorder.start(space_id=SPACE_ID, conversation_id=0)

        assert _run(maker, run_id).conversation_id is None

    def test_long_title_is_clipped(self, scope):
        scope_fn, maker = scope
        recorder = _recorder(scope_fn)

        run_id = recorder.start(space_id=SPACE_ID, title="啊" * 500)

        assert len(_run(maker, run_id).title) == 200

    def test_db_failure_returns_none_without_raising(self):
        """DB 不可用时 `start` 返回 None，后续调用静默跳过。"""

        @contextmanager
        def broken():
            raise RuntimeError("db down")
            yield  # pragma: no cover

        recorder = AgentRunRecorder(session_scope=broken)

        assert recorder.start(space_id=SPACE_ID) is None
        assert recorder.run_id is None
        # 以下调用不得抛出
        recorder.tool_call(
            step=1, seq=1, call_id="c", name="x", args={}, outcome=ToolOutcome(ok=True), duration_ms=1
        )
        recorder.finish(status="completed")


class TestToolCall:
    """工具调用落库：通用列、类型判定与预览截断。"""

    def _start(self, scope) -> tuple[AgentRunRecorder, int, sessionmaker]:
        """启动记录器，返回 `(recorder, run_id, maker)`。"""
        scope_fn, maker = scope
        recorder = _recorder(scope_fn)
        run_id = recorder.start(space_id=SPACE_ID)
        return recorder, run_id, maker

    def test_generic_columns_written(self, scope):
        recorder, run_id, maker = self._start(scope)

        recorder.tool_call(
            step=2,
            seq=3,
            call_id="call_abc",
            name="get_space_endpoints",
            args={"space_id": 1},
            outcome=ToolOutcome(ok=True, text="1 row"),
            duration_ms=42,
        )

        row = _calls(maker, run_id)[0]
        assert row.step_index == 2
        assert row.seq == 3
        assert row.call_id == "call_abc"
        assert row.tool_name == "get_space_endpoints"
        assert row.tool_type == "db"
        assert row.ok == 1
        assert json.loads(row.args_json) == {"space_id": 1}
        assert row.result_preview == "1 row"
        assert row.result_chars == 5
        assert row.duration_ms == 42
        # 非 HTTP 工具：HTTP 列必须全为 NULL，否则视图统计会被污染
        assert row.http_method is None
        assert row.http_url is None

    def test_failure_records_error_type_and_message(self, scope):
        recorder, run_id, maker = self._start(scope)

        recorder.tool_call(
            step=1,
            seq=1,
            call_id="c1",
            name="read_file",
            args={},
            outcome=ToolOutcome(ok=False, error_type="FileNotFoundError", error_message="no such file"),
            duration_ms=5,
        )

        row = _calls(maker, run_id)[0]
        assert row.ok == 0
        assert row.tool_type == "fs"
        assert row.error_type == "FileNotFoundError"
        assert row.error_message == "no such file"

    def test_tool_type_classification(self, scope):
        recorder, run_id, maker = self._start(scope)
        # 名称取自 `src/agent/tools/` 的真实工具，与 `_TOOL_TYPES` 不一致会全部落到 other
        cases = {
            "send_request": "http",
            "list_environments": "http",
            "get_space_endpoints": "db",
            "search_space": "search",
            "read_file": "fs",
            "evaluate_assertions": "exec",
            "recall": "memory",
            "remember": "memory",
            "knowledge_search": "knowledge",
            "read_skill": "skill",
            "list_skills": "skill",
            "memory_future_tool": "memory",  # 前缀兜底
            "mystery_tool": "other",
        }
        for seq, name in enumerate(cases, start=1):
            recorder.tool_call(
                step=1, seq=seq, call_id=f"c{seq}", name=name, args={},
                outcome=ToolOutcome(ok=True, text="{}"), duration_ms=1,
            )

        got = {row.tool_name: row.tool_type for row in _calls(maker, run_id)}
        assert got == cases

    def test_preview_is_clipped_but_result_chars_is_full(self, scope):
        """预览截断到 4000 字，`result_chars` 保留全量长度。"""
        recorder, run_id, maker = self._start(scope)
        text = "x" * 9000

        recorder.tool_call(
            step=1, seq=1, call_id="c", name="read_file", args={},
            outcome=ToolOutcome(ok=True, text=text), duration_ms=1,
        )

        row = _calls(maker, run_id)[0]
        assert len(row.result_preview) == MAX_PREVIEW_CHARS
        assert row.result_chars == 9000

    def test_skipped_when_start_failed(self, scope):
        scope_fn, maker = scope
        recorder = AgentRunRecorder(session_scope=scope_fn)
        # 没有调用 start，run_id 为 None

        recorder.tool_call(
            step=1, seq=1, call_id="c", name="x", args={},
            outcome=ToolOutcome(ok=True), duration_ms=1,
        )

        from src.data.models.agent_tool_call import AgentToolCall

        with maker() as session:
            assert list(session.scalars(select(AgentToolCall))) == []


class TestHttpExtraction:
    """HTTP 工具调用的列提取与请求头脱敏。"""

    def _start(self, scope) -> tuple[AgentRunRecorder, int, sessionmaker]:
        """启动记录器，返回 `(recorder, run_id, maker)`。"""
        scope_fn, maker = scope
        recorder = _recorder(scope_fn)
        run_id = recorder.start(space_id=SPACE_ID)
        return recorder, run_id, maker

    def _http_outcome(self, **overrides) -> ToolOutcome:
        """构造 HTTP 工具成功返回的 JSON 文本。"""
        payload = {
            "status_code": 200,
            "url": "https://api.example.com/v1/orders",
            "headers": {"content-type": "application/json"},
            "body": {"code": 0, "data": []},
        }
        payload.update(overrides)
        return ToolOutcome(ok=True, text=json.dumps(payload))

    def test_http_columns_are_filled(self, scope):
        recorder, run_id, maker = self._start(scope)

        recorder.tool_call(
            step=1, seq=1, call_id="c1", name="send_request",
            args={"method": "post", "url": "https://api.example.com/v1/orders",
                  "headers": {"content-type": "application/json"}, "body": {"page": 1}, "params": {"a": 1}},
            outcome=self._http_outcome(), duration_ms=88,
        )

        row = _calls(maker, run_id)[0]
        assert row.tool_type == "http"
        assert row.http_method == "POST"  # 入参小写要归一为大写
        assert row.http_url == "https://api.example.com/v1/orders"
        assert row.http_status_code == 200
        assert json.loads(row.request_body) == {"page": 1}
        assert json.loads(row.response_body) == {"code": 0, "data": []}
        assert row.response_body_truncated == 0
        assert row.response_size_bytes > 0

    def test_sensitive_headers_are_masked(self, scope):
        recorder, run_id, maker = self._start(scope)

        recorder.tool_call(
            step=1, seq=1, call_id="c1", name="send_request",
            args={
                "method": "GET",
                "headers": {"Authorization": "Bearer super-secret", "Cookie": "sid=abc", "Accept": "*/*"},
            },
            outcome=self._http_outcome(headers={"Set-Cookie": "sid=abc", "Content-Type": "application/json"}),
            duration_ms=10,
        )

        row = _calls(maker, run_id)[0]
        req = json.loads(row.request_headers)
        resp = json.loads(row.response_headers)
        assert req["Authorization"] == "***"
        assert req["Cookie"] == "***"
        assert req["Accept"] == "*/*"
        assert resp["Set-Cookie"] == "***"
        assert resp["Content-Type"] == "application/json"
        # 明文不得出现在任何列
        assert "super-secret" not in (row.request_headers or "")

    def test_oversized_body_is_truncated_and_flagged(self, scope):
        recorder, run_id, maker = self._start(scope)
        huge = "y" * (MAX_RESPONSE_BODY_BYTES + 5_000)

        recorder.tool_call(
            step=1, seq=1, call_id="c1", name="send_request",
            args={"method": "GET"}, outcome=self._http_outcome(body=huge), duration_ms=10,
        )

        row = _calls(maker, run_id)[0]
        assert row.response_body_truncated == 1
        assert len(row.response_body.encode()) <= MAX_RESPONSE_BODY_BYTES + 32  # JSON 引号开销
        # 原始大小需如实记录，截断后长度不可作为依据
        assert row.response_size_bytes > MAX_RESPONSE_BODY_BYTES

    def test_error_only_payload_still_extracts(self, scope):
        """`send_request` 失败时无 `status_code`，仍需保留 url 等痕迹。"""
        recorder, run_id, maker = self._start(scope)

        recorder.tool_call(
            step=1, seq=1, call_id="c1", name="send_request",
            args={"method": "GET"},
            outcome=ToolOutcome(ok=False, error_type="ConnectError", error_message="timeout",
                                text=json.dumps({"error": "timeout", "url": "https://x.dev"})),
            duration_ms=3000,
        )

        row = _calls(maker, run_id)[0]
        assert row.ok == 0
        assert row.http_url == "https://x.dev"
        assert row.http_status_code is None

    def test_non_json_outcome_leaves_http_columns_null(self, scope):
        recorder, run_id, maker = self._start(scope)

        recorder.tool_call(
            step=1, seq=1, call_id="c1", name="send_request",
            args={"method": "GET"},
            outcome=ToolOutcome(ok=True, text="纯文本响应"), duration_ms=10,
        )

        row = _calls(maker, run_id)[0]
        assert row.http_method is None
        assert row.http_url is None


class TestFinish:
    """`finish` 的统计聚合、幂等与异常安全。"""

    def _start(self, scope) -> tuple[AgentRunRecorder, int, sessionmaker]:
        """启动记录器，返回 `(recorder, run_id, maker)`。"""
        scope_fn, maker = scope
        recorder = _recorder(scope_fn)
        run_id = recorder.start(space_id=SPACE_ID)
        return recorder, run_id, maker

    def test_aggregates_tool_stats(self, scope):
        recorder, run_id, maker = self._start(scope)

        for seq, (ok, duration) in enumerate([(True, 100), (True, 200), (False, 300)], start=1):
            recorder.tool_call(
                step=1, seq=seq, call_id=f"c{seq}", name="send_request", args={"method": "GET"},
                outcome=ToolOutcome(ok=ok, text='{"status_code": 200}'), duration_ms=duration,
            )
        recorder.finish(status="completed")

        row = _run(maker, run_id)
        assert row.status == "completed"
        assert row.finished_at is not None
        assert row.tool_call_count == 3
        assert row.ok_count == 2
        assert row.error_count == 1
        assert row.success_rate == pytest.approx(66.67, abs=0.01)
        assert row.avg_response_time == pytest.approx(200.0)
        assert row.duration_ms >= 0

    def test_zero_tools_yields_zero_not_division_error(self, scope):
        recorder, run_id, maker = self._start(scope)

        recorder.finish(status="cancelled")

        row = _run(maker, run_id)
        assert row.status == "cancelled"
        assert row.tool_call_count == 0
        assert row.success_rate == 0.0
        assert row.avg_response_time == 0.0

    def test_cost_is_aggregated_from_llm_log(self, scope):
        recorder, run_id, maker = self._start(scope)

        from src.data.models.llm_log import LLMLog

        with maker() as session:
            session.add(LLMLog(model_name="m1", run_id=run_id, total_tokens=100, cost_usd=0.01))
            session.add(LLMLog(model_name="m1", run_id=run_id, total_tokens=250, cost_usd=0.02))
            # 其他 run 与 run_id 为空的成本不得计入
            session.add(LLMLog(model_name="m1", run_id=run_id + 1, total_tokens=999, cost_usd=9.9))
            session.add(LLMLog(model_name="m1", run_id=None, total_tokens=777, cost_usd=7.7))
            session.commit()

        recorder.finish(status="completed")

        row = _run(maker, run_id)
        assert row.llm_call_count == 2
        assert row.total_tokens == 350
        assert row.cost_usd == pytest.approx(0.03)

    def test_finish_is_idempotent(self, scope):
        recorder, run_id, maker = self._start(scope)

        recorder.finish(status="completed")
        first = _run(maker, run_id)

        recorder.finish(status="failed", error_message="晚到的失败")
        second = _run(maker, run_id)

        # 第二次整条跳过，状态不得被 finally 兜底覆盖
        assert second.status == "completed"
        assert second.finished_at == first.finished_at
        assert second.error_message == ""

    def test_error_message_is_persisted(self, scope):
        recorder, run_id, maker = self._start(scope)

        recorder.finish(status="failed", error_message="网关超时")

        assert _run(maker, run_id).error_message == "网关超时"

    def test_missing_run_row_does_not_raise(self, scope):
        """行被迁移或清理删除后，`finish` 不得抛出。"""
        recorder, _run_id, _maker = self._start(scope)
        recorder.run_id = 999_999_999

        recorder.finish(status="completed")  # 不抛
