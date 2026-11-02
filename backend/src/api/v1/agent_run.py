"""Agent 执行记录路由。

包含查询与清理两部分。清理接口刻意支持 ``dry_run``，因为「删数据」这个
操作在本地单机场景下依然不可逆，先看数量再动手是必要的。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.data.schemas.agent_run import (
    AgentCleanupResult,
    AgentRunDetail,
    AgentRunListResponse,
    AgentRunResponse,
    AgentToolCallBrief,
)
from src.data.schemas.agent_tool_call import (
    AgentToolCallDetail,
    AgentToolCallDetailListResponse,
    AgentToolCallListResponse,
    AgentToolCallResponse,
)
from src.data.services import AgentRunService, AgentToolCallService

router = APIRouter(prefix="/agent/runs", tags=["Agent 执行记录"])


@router.get("/", response_model=AgentRunListResponse)
def list_agent_runs(
    space_id: int | None = Query(default=None, description="空间 ID 筛选"),
    status: str | None = Query(default=None, description="状态筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """查询执行记录列表（分页，按创建时间倒序）。"""
    items, total = AgentRunService(db).list_runs(space_id, status, page, page_size)
    return AgentRunListResponse(
        items=[AgentRunResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ⚠️ 必须定义在 /{run_id} 之前：否则 FastAPI 会把 "cleanup" 当 int 解析并返回 422
@router.delete("/cleanup", response_model=AgentCleanupResult)
def cleanup_agent_runs(
    days: int = Query(default=90, ge=1, le=3650, description="保留最近 N 天"),
    space_id: int | None = Query(default=None, description="只清理指定空间"),
    dry_run: bool = Query(default=False, description="只统计不删除"),
    db: Session = Depends(get_db),
):
    """清理 N 天前的终态执行记录（running 一律不动）。"""
    result = AgentRunService(db).cleanup_runs(days=days, space_id=space_id, dry_run=dry_run)
    return AgentCleanupResult(**result)


@router.get("/{run_id}", response_model=AgentRunDetail)
def get_agent_run(run_id: int, db: Session = Depends(get_db)):
    """获取执行记录详情（含工具调用摘要，不含响应体正文）。"""
    service = AgentRunService(db)
    run = service.get_or_raise(run_id, "执行记录不存在")
    calls = AgentToolCallService(db).list_by_run(run_id)

    return AgentRunDetail(
        **AgentRunResponse.model_validate(run).model_dump(),
        tool_calls=[AgentToolCallBrief.model_validate(c) for c in calls],
    )


@router.get(
    "/{run_id}/tool-calls",
    response_model=None,
    responses={
        200: {
            "description": "默认返回不含正文的摘要；include_body=true 时返回含请求/响应正文的明细",
            "model": AgentToolCallListResponse | AgentToolCallDetailListResponse,
        }
    },
)
def list_agent_tool_calls(
    run_id: int,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页数量"),
    include_body: bool = Query(default=False, description="是否包含请求/响应正文（可能很大）"),
    db: Session = Depends(get_db),
):
    """查询某次执行的工具调用留痕。

    ⚠️ 这里**必须**手工序列化，不能挂固定 ``response_model``：
    ``AgentToolCallResponse`` 本身不含 ``request_body``/``response_body``，
    如果把它当统一响应模型，``include_body=true`` 会被静默吃掉——
    参数接受了、库里也查了，返回体里却永远没有正文。
    """
    AgentRunService(db).get_or_raise(run_id, "执行记录不存在")
    calls = AgentToolCallService(db).list_by_run(run_id, include_body=include_body)

    # service 层不支持分页切片（要保证 include_body 的 defer 生效），这里手工切
    total = len(calls)
    start = (page - 1) * page_size
    page_items = calls[start : start + page_size]

    schema = AgentToolCallDetail if include_body else AgentToolCallResponse
    return {
        "items": [schema.model_validate(c).model_dump() for c in page_items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
