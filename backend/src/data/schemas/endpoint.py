from pydantic import BaseModel, Field, field_validator

from src.data.enum.workflow import HttpMethod
from src.data.schemas.common import (
    BatchDeleteRequest,
    BatchUpdateStatusRequest,
    PaginatedResponse,
    parse_json_field,
)

# ==================== 基础 Schema ====================


class EndpointBase(BaseModel):
    """Endpoint 基础字段"""

    operation_id: str = Field(..., description="操作ID，唯一标识")
    name: str = Field(..., description="API 名称")
    path: str = Field(..., description="API 路径")
    method: str = Field(..., description="HTTP 方法")
    tags: str = Field(default="[]", description="标签列表")
    summary: str | None = Field(default="", description="摘要")
    description: str | None = Field(default="", description="描述")
    params: str | None = Field(default="{}", description="查询参数定义")
    headers: str | None = Field(default="{}", description="请求头定义")
    body: str | None = Field(default="{}", description="请求体定义")
    responses: str = Field(default="[]", description="响应定义 JSON 数组")
    security: str = Field(default="[]", description="接口级认证方案 JSON 数组")
    content_type: str = Field(default="application/json", description="请求体 Content-Type")
    deprecated: int = Field(default=0, description="是否已废弃: 0=正常, 1=已废弃")
    status: int = Field(default=1, description="状态: 1=启用，2=禁用，3=已删除, 4=已废弃")


# ==================== 创建 Schema ====================


class EndpointCreate(EndpointBase):
    """创建 Endpoint 请求体"""

    space_id: int | None = Field(default=None, description="所属空间ID")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "space_id": 1,
                    "operation_id": "getUserById",
                    "name": "获取用户详情",
                    "path": "/api/v1/users/{id}",
                    "method": "GET",
                    "tags": ["用户管理"],
                    "summary": "根据ID获取用户信息",
                    "description": "通过用户ID查询用户详细信息",
                    "params": {"id": {"type": "integer", "required": True, "description": "用户ID"}},
                    "headers": {"Authorization": "Bearer {{token}}"},
                    "body": None,
                    "priority": "P1",
                    "status": 1,
                }
            ]
        }
    }


# ==================== 更新 Schema ====================


class EndpointUpdate(BaseModel):
    """更新 Endpoint 请求体（所有字段可选）"""

    operation_id: str | None = Field(default=None, description="操作ID")
    name: str | None = Field(default=None, description="API 名称")
    path: str | None = Field(default=None, description="API 路径")
    method: HttpMethod | None = Field(default=None, description="HTTP 方法")
    tags: list[str] | None = Field(default=None, description="标签列表")
    summary: str | None = Field(default=None, description="摘要")
    description: str | None = Field(default=None, description="描述")
    params: dict | None = Field(default=None, description="查询参数定义")
    headers: dict | None = Field(default=None, description="请求头定义")
    body: dict | None = Field(default=None, description="请求体定义")
    responses: list | None = Field(default=None, description="响应定义")
    security: list | None = Field(default=None, description="接口级认证方案")
    content_type: str | None = Field(default=None, description="请求体 Content-Type")
    deprecated: int | None = Field(default=None, description="是否已废弃")
    status: int | None = Field(default=None, description="状态")

    @field_validator("tags", "params", "headers", "body", "responses", "security", mode="before")
    @classmethod
    def parse_json_fields(cls, v):
        return parse_json_field(v)


# ==================== 响应 Schema ====================


class EndpointResponse(EndpointBase):
    """Endpoint 响应体"""

    id: int = Field(..., description="Endpoint ID")
    space_id: int = Field(..., description="所属空间ID")
    version: int = Field(default=1, description="版本号")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class EndpointDetail(EndpointResponse):
    """Endpoint 详情响应（含关联的测试用例数量）"""

    test_case_count: int | None = Field(default=0, description="关联测试用例数量")

    model_config = {"from_attributes": True}


# ==================== 列表/分页 Schema ====================


class EndpointListResponse(PaginatedResponse[EndpointResponse]):
    """Endpoint 列表响应"""


class EndpointQuery(BaseModel):
    """Endpoint 查询参数"""

    space_id: int | None = Field(default=None, description="空间ID")
    method: HttpMethod | None = Field(default=None, description="HTTP 方法筛选")
    status: int | None = Field(default=None, description="状态筛选")
    tags: str | None = Field(default=None, description="标签筛选")
    keyword: str | None = Field(default=None, description="关键字搜索(名称/路径/描述)")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


# ==================== 批量操作 Schema ====================


class EndpointBatchDelete(BatchDeleteRequest):
    """批量删除请求"""


class EndpointBatchUpdateStatus(BatchUpdateStatusRequest):
    """批量更新状态请求"""
