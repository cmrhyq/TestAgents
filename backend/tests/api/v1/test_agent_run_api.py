"""Agent 执行记录 API 测试（列表 / 详情 / 留痕 / 清理 / 报告新链路）。

这批接口是「test_* → agent_*」改造后的对外入口，几条关键契约在这里锁死：

1. ``DELETE /agent/runs/cleanup`` 必须命中清理逻辑，**不能**被 ``/{run_id}``
   抢走路由（否则 "cleanup" 会被当 int 解析，直接 422）。
2. ``running`` 状态的记录永远不进清理候选——它可能是进程被 kill 后残留的
   活会话，也可能是正在跑的用户请求。
3. 列表默认不返回 ``response_body``（可能是 MB 级），只有显式
   ``include_body=true`` 才带出来。
4. 报告详情返回的是 ``run``（AgentRunBrief）而不是改造前的 ``test_run``。
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.deps import get_db
from src.data.models.base import Base

SPACE_ID = 8801
OTHER_SPACE_ID = 8802


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'agent_run.db'}")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)

    with maker() as session:
        from src.data.models.space import Space

        session.add(Space(id=SPACE_ID, name="执行记录空间", workspace_path=f"workspaces/{SPACE_ID}"))
        session.add(Space(id=OTHER_SPACE_ID, name="另一个空间", workspace_path=f"workspaces/{OTHER_SPACE_ID}"))
        session.commit()

    yield maker
    engine.dispose()


@pytest.fixture()
def client(factory) -> Generator[TestClient, None, None]:
    def _get_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    from app import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = _get_db
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def seed(factory):
    """插入执行记录 + 工具留痕 + 报告行的工厂。"""

    def _seed_run(
        *,
        run_id: int,
        space_id: int = SPACE_ID,
        status: str = "completed",
        created_at: str = "2026-01-01T10:00:00.000",
        title: str = "查一下订单接口",
    ) -> int:
        from src.data.models.agent_run import AgentRun

        with factory() as session:
            session.add(
                AgentRun(
                    id=run_id,
                    space_id=space_id,
                    title=title,
                    status=status,
                    created_at=created_at,
                    updated_at=created_at,
                    tool_call_count=2,
                    ok_count=1,
                    error_count=1,
                    success_rate=50.0,
                    avg_response_time=120.0,
                )
            )
            session.commit()
        return run_id

    def _seed_tool_call(
        run_id: int,
        *,
        seq: int,
        tool_name: str = "send_request",
        ok: int = 1,
        with_http: bool = True,
        response_body: str = '{"code": 0}',
    ) -> int:
        from src.data.models.agent_tool_call import AgentToolCall

        kwargs = {}
        if with_http:
            kwargs = {
                "http_method": "POST",
                "http_url": "https://api.example.com/v1/orders",
                "http_status_code": 200 if ok else 500,
                "request_headers": '{"content-type": "application/json"}',
                "request_body": '{"page": 1}',
                "response_headers": '{"server": "nginx"}',
                "response_body": response_body,
                "response_size_bytes": len(response_body.encode()),
            }
        with factory() as session:
            row = AgentToolCall(
                run_id=run_id,
                step_index=1,
                seq=seq,
                call_id=f"call_{seq}",
                tool_name=tool_name,
                tool_type="http" if with_http else "db",
                args_json='{"method": "POST"}',
                ok=ok,
                error_type="" if ok else "HTTPError",
                error_message="" if ok else "500 Internal Server Error",
                result_preview=response_body[:100],
                result_chars=len(response_body),
                duration_ms=45,
                **kwargs,
            )
            session.add(row)
            session.commit()
            return row.id

    def _seed_report(run_id: int, *, file_path: str = "reports/agent_1.html") -> int:
        from src.data.models.report import Report

        with factory() as session:
            row = Report(run_id=run_id, format="html", file_path=file_path, file_size=1024)
            session.add(row)
            session.commit()
            return row.id

    return type(
        "Seed",
        (),
        {"run": staticmethod(_seed_run), "tool_call": staticmethod(_seed_tool_call), "report": staticmethod(_seed_report)},
    )


class TestAgentRunList:
    def test_empty_list(self, client):
        response = client.get("/api/v1/agent/runs/")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_returns_new_stat_columns(self, client, seed):
        seed.run(run_id=1001)
        body = client.get("/api/v1/agent/runs/").json()

        item = body["items"][0]
        # 新语义统计列（旧的 pass_rate/total_cases 必须彻底消失）
        assert item["tool_call_count"] == 2
        assert item["ok_count"] == 1
        assert item["error_count"] == 1
        assert item["success_rate"] == 50.0
        assert item["avg_response_time"] == 120.0
        assert "pass_rate" not in item
        assert "total_cases" not in item

    def test_filter_by_space_and_status(self, client, seed):
        seed.run(run_id=1002, space_id=SPACE_ID, status="completed")
        seed.run(run_id=1003, space_id=OTHER_SPACE_ID, status="completed")
        seed.run(run_id=1004, space_id=SPACE_ID, status="failed")

        by_space = client.get("/api/v1/agent/runs/", params={"space_id": SPACE_ID}).json()
        assert {i["id"] for i in by_space["items"]} == {1002, 1004}

        by_status = client.get("/api/v1/agent/runs/", params={"status": "failed"}).json()
        assert {i["id"] for i in by_status["items"]} == {1004}

    def test_sorted_by_created_at_desc(self, client, seed):
        seed.run(run_id=1005, created_at="2026-01-01T10:00:00.000")
        seed.run(run_id=1006, created_at="2026-03-01T10:00:00.000")
        seed.run(run_id=1007, created_at="2026-02-01T10:00:00.000")

        items = client.get("/api/v1/agent/runs/").json()["items"]
        assert [i["id"] for i in items] == [1006, 1007, 1005]

    def test_pagination(self, client, seed):
        for index in range(5):
            seed.run(run_id=1100 + index, created_at=f"2026-01-0{index + 1}T10:00:00.000")

        page2 = client.get("/api/v1/agent/runs/", params={"page": 2, "page_size": 2}).json()
        assert page2["total"] == 5
        assert len(page2["items"]) == 2
        # 倒序的第 2 页 = 第 3、4 条（1102、1101）
        assert [i["id"] for i in page2["items"]] == [1102, 1101]


class TestAgentRunDetail:
    def test_detail_embeds_tool_call_briefs(self, client, seed):
        seed.run(run_id=1200)
        seed.tool_call(1200, seq=1, ok=1)
        seed.tool_call(1200, seq=2, ok=0)

        response = client.get("/api/v1/agent/runs/1200")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["id"] == 1200
        assert body["title"] == "查一下订单接口"
        assert len(body["tool_calls"]) == 2
        first = body["tool_calls"][0]
        assert first["seq"] == 1
        assert first["tool_name"] == "send_request"
        assert first["http_method"] == "POST"
        # 摘要不带正文
        assert "request_body" not in first
        assert "response_body" not in first

    def test_detail_404(self, client):
        response = client.get("/api/v1/agent/runs/999999")

        assert response.status_code == 404, response.text


class TestAgentToolCallList:
    def test_excludes_body_by_default(self, client, seed):
        seed.run(run_id=1300)
        seed.tool_call(1300, seq=1, response_body='{"code": 0}')

        body = client.get("/api/v1/agent/runs/1300/tool-calls").json()

        assert body["total"] == 1
        item = body["items"][0]
        # 默认口径是「字段不存在」而不是「字段为 null」——null 会让人误以为
        # 这次调用真的没有请求体，而实际只是没查回来。
        assert "request_body" not in item
        assert "response_body" not in item
        assert "args_json" not in item
        assert item["response_size_bytes"] == len('{"code": 0}')

    def test_include_body_true_returns_content(self, client, seed):
        seed.run(run_id=1301)
        seed.tool_call(1301, seq=1, response_body='{"code": 0, "data": []}')

        body = client.get("/api/v1/agent/runs/1301/tool-calls", params={"include_body": True}).json()

        item = body["items"][0]
        assert item["request_body"] == '{"page": 1}'
        assert item["response_body"] == '{"code": 0, "data": []}'

    def test_non_http_tool_has_null_http_columns(self, client, seed):
        seed.run(run_id=1302)
        seed.tool_call(1302, seq=1, tool_name="query_db", with_http=False)

        item = client.get("/api/v1/agent/runs/1302/tool-calls").json()["items"][0]

        assert item["tool_type"] == "db"
        assert item["http_url"] is None
        assert item["http_status_code"] is None

    def test_404_when_run_missing(self, client):
        response = client.get("/api/v1/agent/runs/999998/tool-calls")

        assert response.status_code == 404, response.text


class TestCleanupRoute:
    def test_cleanup_route_not_shadowed_by_run_id(self, client):
        """路由顺序回归：/cleanup 若排在 /{run_id} 之后会被解析成 int 并 422。"""
        response = client.delete("/api/v1/agent/runs/cleanup", params={"dry_run": True})

        assert response.status_code == 200, response.text
        assert "cutoff" in response.json()

    def test_dry_run_deletes_nothing(self, client, seed):
        seed.run(run_id=1400, created_at="2020-01-01T00:00:00.000", status="completed")

        body = client.delete("/api/v1/agent/runs/cleanup", params={"days": 90, "dry_run": True}).json()

        assert body["dry_run"] is True
        assert body["deleted_runs"] == 1
        assert body["deleted_tool_calls"] == 0
        # 试运行不真删
        assert client.get("/api/v1/agent/runs/").json()["total"] == 1

    def test_real_cleanup_removes_old_terminal_runs(self, client, seed):
        seed.run(run_id=1401, created_at="2020-01-01T00:00:00.000", status="completed")
        seed.tool_call(1401, seq=1)
        seed.report(1401, file_path="reports/old_1401.html")

        body = client.delete("/api/v1/agent/runs/cleanup", params={"days": 90}).json()

        assert body["deleted_runs"] == 1
        assert body["deleted_tool_calls"] == 1
        assert body["deleted_reports"] == 1
        # 报告文件不代删，只报路径
        assert body["orphan_files"] == ["reports/old_1401.html"]
        assert client.get("/api/v1/agent/runs/").json()["total"] == 0
        assert client.get("/api/v1/agent/runs/1401").status_code == 404

    def test_running_runs_never_cleaned(self, client, seed):
        seed.run(run_id=1402, created_at="2020-01-01T00:00:00.000", status="running")

        body = client.delete("/api/v1/agent/runs/cleanup", params={"days": 1}).json()

        assert body["deleted_runs"] == 0
        assert client.get("/api/v1/agent/runs/").json()["total"] == 1

    def test_recent_runs_survive_cleanup(self, client, seed):
        from src.data.models.base import local_now

        seed.run(run_id=1403, created_at=local_now(), status="completed")

        body = client.delete("/api/v1/agent/runs/cleanup", params={"days": 90}).json()

        assert body["deleted_runs"] == 0
        assert client.get("/api/v1/agent/runs/").json()["total"] == 1

    def test_space_scoped_cleanup(self, client, seed):
        seed.run(run_id=1404, space_id=SPACE_ID, created_at="2020-01-01T00:00:00.000")
        seed.run(run_id=1405, space_id=OTHER_SPACE_ID, created_at="2020-01-01T00:00:00.000")

        body = client.delete("/api/v1/agent/runs/cleanup", params={"days": 90, "space_id": SPACE_ID}).json()

        assert body["deleted_runs"] == 1
        remaining = client.get("/api/v1/agent/runs/").json()["items"]
        assert [i["id"] for i in remaining] == [1405]


class TestReportRelink:
    def test_report_list_exposes_run_title(self, client, seed):
        seed.run(run_id=1500, title="验证下单链路")
        seed.report(1500)

        body = client.get("/api/v1/reports/").json()

        assert body["total"] == 1
        item = body["items"][0]
        assert item["run_id"] == 1500
        assert item["run_title"] == "验证下单链路"
        assert "test_run_name" not in item

    def test_report_detail_returns_run_and_tool_calls(self, client, seed):
        seed.run(run_id=1501, title="验证退款链路")
        seed.tool_call(1501, seq=1)
        report_id = seed.report(1501)

        body = client.get(f"/api/v1/reports/{report_id}").json()

        assert "test_run" not in body
        assert body["run"]["id"] == 1501
        assert body["run"]["title"] == "验证退款链路"
        assert body["run"]["success_rate"] == 50.0
        assert len(body["tool_calls"]) == 1
        assert body["tool_calls"][0]["response_body"] == '{"code": 0}'

    def test_deleting_run_cascades_report_rows(self, client, seed):
        """report.run_id 外键指向 agent_run，清 run 时报告行随之消失。"""
        seed.run(run_id=1502, created_at="2020-01-01T00:00:00.000")
        seed.report(1502)

        client.delete("/api/v1/agent/runs/cleanup", params={"days": 90})

        assert client.get("/api/v1/reports/").json()["total"] == 0
