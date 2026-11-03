from pydantic import BaseModel, Field

from src.data.schemas.common import (
    BatchDeleteRequest,
    BatchUpdateStatusRequest,
    PaginatedResponse,
)

# ==================== 基础 Schema ====================


class SpaceBase(BaseModel):
    """空间基础字段。"""

    name: str = Field(..., min_length=1, max_length=100, description="空间名称，全库唯一")
    description: str | None = Field(default="", description="空间描述")
    status: int = Field(default=1, description="状态：1-启用，2-禁用")


# ==================== 创建 Schema ====================


class SpaceCreate(SpaceBase):
    """创建空间请求体。"""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "用户服务",
                    "description": "用户中心微服务",
                    "status": 1,
                }
            ]
        }
    }


# ==================== 更新 Schema ====================


class SpaceUpdate(BaseModel):
    """更新空间请求体，所有字段可选。"""

    name: str | None = Field(default=None, min_length=1, max_length=100, description="空间名称")
    description: str | None = Field(default=None, description="空间描述")
    status: int | None = Field(default=None, description="状态：1-启用，2-禁用")


# ==================== 响应 Schema ====================


class SpaceResponse(SpaceBase):
    """空间响应体。"""

    id: int = Field(..., description="空间 ID")
    workspace_path: str = Field(default="", description="工作目录路径，相对 backend 根")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class SpaceDetail(SpaceResponse):
    """空间详情响应，附带统计信息。"""

    endpoint_count: int | None = Field(default=0, description="空间下的接口数")
    test_run_count: int | None = Field(default=0, description="空间的执行记录数")

    model_config = {"from_attributes": True}


# ==================== 列表/分页 Schema ====================


class SpaceListResponse(PaginatedResponse[SpaceResponse]):
    """空间列表响应。"""


class SpaceQuery(BaseModel):
    """空间查询参数。"""

    name: str | None = Field(default=None, description="空间名称，模糊匹配")
    status: int | None = Field(default=None, description="状态筛选")
    keyword: str | None = Field(default=None, description="关键字，匹配名称或描述")
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页记录数，1-100")


# ==================== 批量操作 Schema ====================


class SpaceBatchDelete(BatchDeleteRequest):
    """批量删除空间请求体。"""


class SpaceBatchUpdateStatus(BatchUpdateStatusRequest):
    """批量更新空间状态请求体。"""
