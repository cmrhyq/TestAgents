"""空间管理路由：空间增删改查、OpenAPI 文档导入、工作目录与 ``AGENTS.md`` 读写。

空间删除为软归档，磁盘目录改名为 ``.deleted-{timestamp}`` 而非物理删除。
"""

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
    """创建空间，并同步初始化其工作目录骨架。

    Args:
        body: 空间名称与描述
        db: 请求级数据库会话

    Returns:
        新建空间详情，HTTP 201

    Raises:
        ConflictError: 空间名称已存在，返回 HTTP 409
    """
    return SpaceService(db).create_space(body)


@router.get("/", response_model=SpaceListResponse)
def list_spaces(
    keyword: str | None = Query(default=None, description="关键字搜索"),
    status: int | None = Query(default=None, description="状态筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """分页查询空间列表。

    Args:
        keyword: 按名称或描述模糊匹配，不传则不过滤
        status: 状态过滤值，不传则不过滤
        page: 页码，从 1 开始
        page_size: 每页条数，取值 1-100
        db: 请求级数据库会话

    Returns:
        当页空间列表与总数
    """
    items, total = SpaceService(db).list_spaces(keyword, status, page, page_size)
    return SpaceListResponse(
        items=[SpaceResponse.model_validate(p) for p in items], total=total, page=page, page_size=page_size
    )


class ParseOpenAPIRequest(BaseModel):
    """OpenAPI 文档解析结果。"""

    run_id: int | None = None
    status: str = TestStatus.COMPLETED.value
    message: str = ""
    endpoints_count: int = 0


@router.get("/{space_id}", response_model=SpaceResponse)
def get_space(space_id: int, db: Session = Depends(get_db)):
    """按 ID 查询空间详情。

    Args:
        space_id: 空间 ID
        db: 请求级数据库会话

    Returns:
        空间详情

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
    """
    return SpaceService(db).get_or_raise(space_id, "空间不存在")


@router.put("/{space_id}", response_model=SpaceResponse)
def update_space(space_id: int, body: SpaceUpdate, db: Session = Depends(get_db)):
    """局部更新空间，仅提交的字段生效。

    Args:
        space_id: 空间 ID
        body: 待更新字段，未传字段保持原值
        db: 请求级数据库会话

    Returns:
        更新后的空间详情

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
        ConflictError: 新名称与其他空间重名，返回 HTTP 409
    """
    return SpaceService(db).update_space(space_id, body.model_dump(exclude_unset=True))


@router.delete("/{space_id}", status_code=204)
def delete_space(space_id: int, db: Session = Depends(get_db)):
    """删除空间，级联删除其环境、接口、执行记录等数据。

    工作目录仅归档改名，磁盘文件保留以便恢复。

    Args:
        space_id: 空间 ID
        db: 请求级数据库会话

    Returns:
        无响应体，HTTP 204

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
    """
    SpaceService(db).delete_space(space_id)


@router.post("/parse/openapi/{space_id}", response_model=ParseOpenAPIRequest)
async def parse_openapi(
        space_id: int,
        file: UploadFile = File(..., description="OpenAPI 文档文件（JSON/YAML）"),
):
    """上传并解析 OpenAPI 文档，将接口定义写入该空间。

    解析在线程池中执行，避免阻塞事件循环。

    Args:
        space_id: 目标空间 ID
        file: OpenAPI 文档文件，支持 JSON 与 YAML

    Returns:
        解析结果，含成功状态、提示信息与导入的接口数量

    Raises:
        ValidationError: 文件名为空、后缀非 JSON/YAML 或解析失败，返回 HTTP 422
    """
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
    """返回空间工作目录树，供前端「概览」页展示。

    目录不存在时会先按默认骨架创建。

    Args:
        space_id: 空间 ID
        max_depth: 展开层数，取值 1-6；不传则取配置值
        db: 请求级数据库会话

    Returns:
        含 ``space_id``、根目录名与 ``nodes`` 树的字典

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
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
    """``AGENTS.md`` 覆盖写入请求体。"""

    content: str = Field(..., description="AGENTS.md 全文")


@router.get("/{space_id}/agents-md")
def get_agents_md(space_id: int, db: Session = Depends(get_db)):
    """读取空间 ``AGENTS.md`` 全文。

    该文件内容会作为空间级约定注入 system prompt。

    Args:
        space_id: 空间 ID
        db: 请求级数据库会话

    Returns:
        ``{"content": 正文}``；文件不存在时 content 为空字符串

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
    """
    SpaceService(db).get_or_raise(space_id, "空间不存在")
    manager = get_workspace_manager()
    manager.ensure(space_id)
    path = manager.resolve(space_id, "AGENTS.md")
    return {"content": path.read_text(encoding="utf-8") if path.is_file() else ""}


@router.put("/{space_id}/agents-md")
def update_agents_md(space_id: int, body: AgentsMdBody, db: Session = Depends(get_db)):
    """覆盖写入空间 ``AGENTS.md``，下一轮对话生效。

    Args:
        space_id: 空间 ID
        body: 文件全文
        db: 请求级数据库会话

    Returns:
        ``{"ok": True, "length": 写入字符数}``

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
    """
    SpaceService(db).get_or_raise(space_id, "空间不存在")
    manager = get_workspace_manager()
    manager.ensure(space_id)
    manager.resolve(space_id, "AGENTS.md").write_text(body.content, encoding="utf-8")
    return {"ok": True, "length": len(body.content)}