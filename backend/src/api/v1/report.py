"""测试报告路由。

报告 = 一次执行（``run_id``）里所有 ``send_request`` 的请求/响应汇总。
数据源是 ``agent_tool_call``，不再有独立的 report 表与报告文件。

三个接口的分工（也是为了不把详情页撑爆）：

1. ``GET /reports/``            一行一个 run，带聚合读数
2. ``GET /reports/{run_id}``    本次执行的请求清单，**不含正文**
3. ``GET /reports/{run_id}/requests/{request_id}``  单条正文，展开时才拉
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.data.models.agent_tool_call import AgentToolCall
from src.data.schemas.agent_run import AgentRunBrief
from src.data.schemas.agent_tool_call import AgentToolCallDetail, AgentToolCallResponse
from src.data.schemas.report import (
    ReportDetailResponse,
    ReportListResponse,
    ReportResponse,
    ReportStat,
)
from src.data.services import AgentRunService, AgentToolCallService

router = APIRouter(prefix="/reports", tags=["测试报告"])


def _is_success(call: AgentToolCall) -> bool:
    """HTTP 2xx 才算成功——口径与 ``ReportStat.success_count`` 保持一致。"""
    code = call.http_status_code
    return code is not None and 200 <= code <= 299


def _stat_from_calls(calls: list[AgentToolCall]) -> ReportStat:
    """从请求清单就地算统计，避免详情页再打一次聚合查询。"""
    total = len(calls)
    success = sum(1 for call in calls if _is_success(call))
    # 没有状态码 = 根本没拿到响应（网络异常 / 参数不合法 / 生产环境被拦截）。
    # 不能看 ok：send_request 返回 {"error": ...} 时工具层仍记为成功。
    exception = sum(1 for call in calls if call.http_status_code is None)
    durations = [call.duration_ms for call in calls]

    return ReportStat(
        request_count=total,
        success_count=success,
        # 非 2xx 但拿到了响应的次数：total - success 里再剔掉「连响应都没有」的
        error_count=max(total - success - exception, 0),
        exception_count=exception,
        success_rate=round(success / total * 100, 2) if total else 0.0,
        avg_duration_ms=round(sum(durations) / total, 2) if total else 0.0,
        first_request_at=min((call.created_at for call in calls), default=None),
        last_request_at=max((call.created_at for call in calls), default=None),
    )


@router.get("/", response_model=ReportListResponse)
def list_reports(
    space_id: int | None = Query(default=None, description="按空间 ID 筛选"),
    status: str | None = Query(default=None, description="按执行状态筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """查询报告列表：按 ``run_id`` 聚合 send_request，只含有 HTTP 请求的执行。"""
    rows, total = AgentToolCallService(db).list_http_run_stats(space_id, status, page, page_size)

    items = []
    for row in rows:
        request_count = int(row.request_count or 0)
        success_count = int(row.success_count or 0)
        exception_count = int(row.exception_count or 0)
        items.append(
            ReportResponse(
                run_id=row.run_id,
                title=row.title or "",
                status=row.status or "",
                mode=row.mode or "",
                space_id=row.space_id,
                run_created_at=row.run_created_at or "",
                request_count=request_count,
                success_count=success_count,
                error_count=max(request_count - success_count - exception_count, 0),
                exception_count=exception_count,
                success_rate=round(success_count / request_count * 100, 2) if request_count else 0.0,
                avg_duration_ms=round(float(row.avg_duration_ms or 0.0), 2),
                first_request_at=row.first_request_at,
                last_request_at=row.last_request_at,
            )
        )

    return ReportListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{run_id}", response_model=ReportDetailResponse)
def get_report_detail(run_id: int, db: Session = Depends(get_db)):
    """报告详情：执行摘要 + 统计 + 请求清单（不含请求/响应正文）。"""
    run = AgentRunService(db).get_or_raise(run_id, "执行记录不存在")
    calls = AgentToolCallService(db).list_http_requests(run_id)

    return ReportDetailResponse(
        run=AgentRunBrief.model_validate(run),
        stat=_stat_from_calls(calls),
        requests=[AgentToolCallResponse.model_validate(call) for call in calls],
    )


@router.get("/{run_id}/requests/{request_id}", response_model=AgentToolCallDetail)
def get_report_request(run_id: int, request_id: int, db: Session = Depends(get_db)):
    """单条请求的完整请求/响应正文（详情页展开某一行时懒加载）。"""
    call = AgentToolCallService(db).get_http_request_or_raise(run_id, request_id)
    return AgentToolCallDetail.model_validate(call)
