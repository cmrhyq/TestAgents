"""接口管理路由：接口定义的增删改查与批量导入。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.data.schemas.endpoint import (
    EndpointCreate,
    EndpointListResponse,
    EndpointResponse,
    EndpointUpdate,
)
from src.data.services import EndpointService

router = APIRouter(prefix="/endpoints", tags=["接口管理"])


@router.post("/", response_model=EndpointResponse, status_code=201)
def create_endpoint(body: EndpointCreate, db: Session = Depends(get_db)):
    """创建单个接口定义。

    Args:
        body: 接口所属空间、路径、方法、请求与响应结构
        db: 请求级数据库会话

    Returns:
        新建接口详情，HTTP 201
    """
    return EndpointService(db).create_one(body)


@router.post("/batch", response_model=list[EndpointResponse], status_code=201)
def batch_create_endpoints(body: list[EndpointCreate], db: Session = Depends(get_db)):
    """批量创建接口定义。

    Args:
        body: 接口定义列表，单次请求一次性写入
        db: 请求级数据库会话

    Returns:
        新建接口详情列表，HTTP 201
    """
    return EndpointService(db).create_endpoint(body)


@router.get("/", response_model=EndpointListResponse)
def list_endpoints(
    space_id: int | None = Query(default=None, description="空间ID筛选"),
    method: str | None = Query(default=None, description="HTTP 方法筛选"),
    keyword: str | None = Query(default=None, description="关键字搜索"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """分页查询接口列表。

    Args:
        space_id: 按空间过滤，不传则跨空间查询
        method: 按 HTTP 方法过滤，如 ``GET``
        keyword: 按路径或名称模糊匹配
        page: 页码，从 1 开始
        page_size: 每页条数，取值 1-100
        db: 请求级数据库会话

    Returns:
        当页接口列表与总数
    """
    items, total = EndpointService(db).list_endpoints(space_id, method, keyword, page, page_size)
    return EndpointListResponse(
        items=[EndpointResponse.model_validate(e) for e in items], total=total, page=page, page_size=page_size
    )


@router.get("/{endpoint_id}", response_model=EndpointResponse)
def get_endpoint(endpoint_id: int, db: Session = Depends(get_db)):
    """按 ID 查询接口详情。

    Args:
        endpoint_id: 接口 ID
        db: 请求级数据库会话

    Returns:
        接口详情

    Raises:
        NotFoundError: 接口不存在，返回 HTTP 404
    """
    return EndpointService(db).get_or_raise(endpoint_id, "接口不存在")


@router.put("/{endpoint_id}", response_model=EndpointResponse)
def update_endpoint(endpoint_id: int, body: EndpointUpdate, db: Session = Depends(get_db)):
    """局部更新接口定义，仅提交的字段生效。

    Args:
        endpoint_id: 接口 ID
        body: 待更新字段
        db: 请求级数据库会话

    Returns:
        更新后的接口详情

    Raises:
        NotFoundError: 接口不存在，返回 HTTP 404
    """
    return EndpointService(db).update_endpoint(endpoint_id, body.model_dump(exclude_unset=True))


@router.delete("/{endpoint_id}", status_code=204)
def delete_endpoint(endpoint_id: int, db: Session = Depends(get_db)):
    """删除接口定义。

    Args:
        endpoint_id: 接口 ID
        db: 请求级数据库会话

    Returns:
        无响应体，HTTP 204

    Raises:
        NotFoundError: 接口不存在，返回 HTTP 404
    """
    EndpointService(db).delete(endpoint_id)
