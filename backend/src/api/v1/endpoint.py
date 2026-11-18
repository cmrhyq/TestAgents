"""接口管理路由：接口定义的增删改查与批量导入。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.data.schemas.endpoint import (
    EndpointCreate,
    EndpointListResponse,
    EndpointResponse,
    EndpointTagFacet,
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
    keyword: str | None = Query(default=None, description="关键字搜索，覆盖名称、路径、摘要、方法与标签"),
    tags: str | None = Query(default=None, description="标签筛选，多个用英文逗号分隔，如 `用户,鉴权`"),
    tags_mode: str = Query(default="any", pattern="^(any|all)$", description="标签匹配方式：any 命中任一，all 需全部命中"),
    status: int | None = Query(default=None, description="数据状态筛选，不传则不过滤"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """分页查询接口列表。

    Args:
        space_id: 按空间过滤，不传则跨空间查询
        method: 按 HTTP 方法过滤，如 ``GET``
        keyword: 按名称、路径、摘要、方法或标签模糊匹配
        tags: 按标签过滤，英文逗号分隔；空字符串等同不过滤
        tags_mode: 多标签时的匹配方式，``any`` 命中任一，``all`` 需全部命中
        status: 按数据状态过滤，不传则包含全部状态
        page: 页码，从 1 开始
        page_size: 每页条数，取值 1-100
        db: 请求级数据库会话

    Returns:
        当页接口列表与总数
    """
    tag_list = [tag.strip() for tag in (tags or "").split(",") if tag.strip()]
    items, total = EndpointService(db).list_endpoints(
        space_id,
        method,
        keyword,
        page,
        page_size,
        tags=tag_list,
        tags_mode=tags_mode,
        status=status,
    )
    return EndpointListResponse(
        items=[EndpointResponse.model_validate(e) for e in items], total=total, page=page, page_size=page_size
    )


@router.get("/tags", response_model=list[EndpointTagFacet])
def list_endpoint_tags(
    space_id: int = Query(..., description="空间 ID，标签统计按空间隔离"),
    db: Session = Depends(get_db),
):
    """列出空间内的标签及其接口数量。

    供接口列表的标签筛选器与表单的标签联想使用。分页查询无法在前端汇总出全量
    标签，因此单独提供聚合接口。

    Args:
        space_id: 空间主键
        db: 请求级数据库会话

    Returns:
        标签聚合列表，按接口数降序排列
    """
    facets = EndpointService(db).list_tag_facets(space_id)
    return [EndpointTagFacet(name=name, count=count) for name, count in facets]


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
