"""空间管理路由。"""

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from src.data.enum import TestStatus
from src.data.services.workflow_service import WorkflowService
from src.api.deps import get_db
from src.data.schemas.space import (
    SpaceCreate,
    SpaceListResponse,
    SpaceResponse,
    SpaceUpdate,
)
from src.data.services import SpaceService
from src.workspace.manager import get_workspace_manager

router = APIRouter(prefix="/spaces", tags=["空间管理"])


@router.post("/", response_model=SpaceResponse, status_code=201)
def create_space(body: SpaceCreate, db: Session = Depends(get_db)):
    """创建空间。"""
    return SpaceService(db).create_space(body)


@router.get("/", response_model=SpaceListResponse)
def list_spaces(
    keyword: str | None = Query(default=None, description="关键字搜索"),
    status: int | None = Query(default=None, description="状态筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """查询空间列表（分页）。"""
    items, total = SpaceService(db).list_spaces(keyword, status, page, page_size)
    return SpaceListResponse(
        items=[SpaceResponse.model_validate(p) for p in items], total=total, page=page, page_size=page_size
    )


class ParseOpenAPIRequest(BaseModel):
    """解析 OpenAPI 文档响应体。"""

    run_id: int | None = None
    status: str = TestStatus.COMPLETED.value
    message: str = ""
    endpoints_count: int = 0


@router.get("/{space_id}", response_model=SpaceResponse)
def get_space(space_id: int, db: Session = Depends(get_db)):
    """获取空间详情。"""
    return SpaceService(db).get_or_raise(space_id, "空间不存在")


@router.put("/{space_id}", response_model=SpaceResponse)
def update_space(space_id: int, body: SpaceUpdate, db: Session = Depends(get_db)):
    """更新空间。"""
    return SpaceService(db).update_space(space_id, body.model_dump(exclude_unset=True))


@router.delete("/{space_id}", status_code=204)
def delete_space(space_id: int, db: Session = Depends(get_db)):
    """删除空间及其关联的环境、端点、测试运行等数据。"""
    SpaceService(db).delete_space(space_id)


@router.post("/parse/openapi/{space_id}", response_model=ParseOpenAPIRequest)
async def parse_openapi(
        space_id: int,
        file: UploadFile = File(..., description="OpenAPI 文档文件（JSON/YAML）"),
):
    """上传并解析 OpenAPI 文档，将接口定义存入数据库。"""
    service = WorkflowService()
    content = await file.read()
    result = await run_in_threadpool(service.parse_openapi, space_id, file.filename or "", content)

    return ParseOpenAPIRequest(
        status=TestStatus.COMPLETED.value,
        message=f"文档 {file.filename} 解析成功",
        endpoints_count=result["endpoint_count"],
    )


# ─── 工作目录 ────────────────────────────────────────────────────────────


@router.get("/{space_id}/tree")
def get_workspace_tree(
    space_id: int,
    max_depth: int | None = Query(default=None, ge=1, le=6, description="展开层数，默认取配置"),
    db: Session = Depends(get_db),
):
    """返回空间工作目录树。

    目录是 Agent 的沙箱，前端「概览」页用它展示空间里都有什么文件。
    """
    SpaceService(db).get_or_raise(space_id, "空间不存在")
    manager = get_workspace_manager()
    manager.ensure(space_id)
    return {
        "space_id": space_id,
        "root": manager.space_dir(space_id).name,
        "nodes": manager.tree(space_id, max_depth),
    }


class AgentsMdBody(BaseModel):
    """空间级智能体指令编辑请求体。"""

    content: str = Field(..., description="AGENTS.md 全文")


@router.get("/{space_id}/agents-md")
def get_agents_md(space_id: int, db: Session = Depends(get_db)):
    """读取空间的 AGENTS.md（会被注入 system prompt）。"""
    SpaceService(db).get_or_raise(space_id, "空间不存在")
    manager = get_workspace_manager()
    manager.ensure(space_id)
    path = manager.resolve(space_id, "AGENTS.md")
    return {"content": path.read_text(encoding="utf-8") if path.is_file() else ""}


@router.put("/{space_id}/agents-md")
def update_agents_md(space_id: int, body: AgentsMdBody, db: Session = Depends(get_db)):
    """覆盖写入 AGENTS.md。下一轮对话即生效，无需重启。"""
    SpaceService(db).get_or_raise(space_id, "空间不存在")
    manager = get_workspace_manager()
    manager.ensure(space_id)
    manager.resolve(space_id, "AGENTS.md").write_text(body.content, encoding="utf-8")
    return {"ok": True, "length": len(body.content)}