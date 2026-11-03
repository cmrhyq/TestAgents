"""Agent 执行记录路由：查询执行记录与工具调用留痕、清理历史记录。

清理接口支持 ``dry_run``，先统计数量再决定是否删除。
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
    """分页查询执行记录列表，按创建时间倒序。

    Args:
        space_id: 按空间过滤，不传则全站查询
        status: 按状态过滤，如 ``completed``
        page: 页码，从 1 开始
        page_size: 每页条数，取值 1-100
        db: 请求级数据库会话

    Returns:
        当页执行记录与总数
    """
    items, total = AgentRunService(db).list_runs(space_id, status, page, page_size)
    return AgentRunListResponse(
        items=[AgentRunResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# 必须定义在 /{run_id} 之前：否则 FastAPI 会把 "cleanup" 当 int 解析并返回 422
@router.delete("/cleanup", response_model=AgentCleanupResult)
def cleanup_agent_runs(
    days: int = Query(default=90, ge=1, le=3650, description="保留最近 N 天"),
    space_id: int | None = Query(default=None, description="只清理指定空间"),
    dry_run: bool = Query(default=False, description="只统计不删除"),
    db: Session = Depends(get_db),
):
    """清理指定天数之前的终态执行记录，运行中的记录不会被删除。

    Args:
        days: 保留最近多少天，取值 1-3650
        space_id: 只清理该空间的记录，不传则全站清理
        dry_run: 为 True 时只返回统计结果，不实际删除
        db: 请求级数据库会话

    Returns:
        清理结果：截止时间、删除的执行记录/工具调用/报告数量，以及磁盘残留的报告文件路径
    """
    result = AgentRunService(db).cleanup_runs(days=days, space_id=space_id, dry_run=dry_run)
    return AgentCleanupResult(**result)


@router.get("/{run_id}", response_model=AgentRunDetail)
def get_agent_run(run_id: int, db: Session = Depends(get_db)):
    """查询执行记录详情，附工具调用摘要。

    Args:
        run_id: 执行记录 ID
        db: 请求级数据库会话

    Returns:
        执行记录详情与工具调用摘要列表；摘要不含请求/响应正文

    Raises:
        NotFoundError: 执行记录不存在，返回 HTTP 404
    """
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
    """分页查询某次执行的工具调用留痕。

    响应模型按 ``include_body`` 在 ``AgentToolCallListResponse`` 与
    ``AgentToolCallDetailListResponse`` 之间切换；``AgentToolCallResponse``
    不含正文字段，不能作为统一响应模型，否则 ``include_body=true`` 时正文会被丢弃。

    Args:
        run_id: 执行记录 ID
        page: 页码，从 1 开始
        page_size: 每页条数，取值 1-200
        include_body: 是否返回请求/响应正文，正文可能很大
        db: 请求级数据库会话

    Returns:
        ``{"items", "total", "page", "page_size"}``

    Raises:
        NotFoundError: 执行记录不存在，返回 HTTP 404
    """
    AgentRunService(db).get_or_raise(run_id, "执行记录不存在")
    calls = AgentToolCallService(db).list_by_run(run_id, include_body=include_body)

    # service 层不支持分页切片（要保持 include_body 的 defer 生效），这里手工切
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
