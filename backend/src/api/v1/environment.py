"""环境管理路由。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.data.schemas.environment import (
    EnvironmentCreate,
    EnvironmentListResponse,
    EnvironmentResponse,
    EnvironmentUpdate,
)
from src.data.services import EnvironmentService

router = APIRouter(prefix="/environments", tags=["环境管理"])


@router.post("/", response_model=EnvironmentResponse, status_code=201)
def create_environment(body: EnvironmentCreate, db: Session = Depends(get_db)):
    """创建环境配置。"""
    return EnvironmentService(db).create_environment(body)


@router.get("/", response_model=EnvironmentListResponse)
def list_environments(
    space_id: int | None = Query(default=None, description="空间ID筛选"),
    keyword: str | None = Query(default=None, description="关键字搜索"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """查询环境列表（分页）。"""
    items, total = EnvironmentService(db).list_environments(space_id, keyword, page, page_size)
    return EnvironmentListResponse(
        items=[EnvironmentResponse.model_validate(e) for e in items], total=total, page=page, page_size=page_size
    )


@router.get("/{env_id}", response_model=EnvironmentResponse)
def get_environment(env_id: int, db: Session = Depends(get_db)):
    """获取环境详情。"""
    return EnvironmentService(db).get_or_raise(env_id, "环境不存在")


@router.put("/{env_id}", response_model=EnvironmentResponse)
def update_environment(env_id: int, body: EnvironmentUpdate, db: Session = Depends(get_db)):
    """更新环境配置。"""
    return EnvironmentService(db).update_environment(env_id, body.model_dump(exclude_unset=True))


@router.delete("/{env_id}", status_code=204)
def delete_environment(env_id: int, db: Session = Depends(get_db)):
    """删除环境。"""
    EnvironmentService(db).delete(env_id)
