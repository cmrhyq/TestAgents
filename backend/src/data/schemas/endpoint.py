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
    """接口基础字段。"""

    operation_id: str = Field(..., description="操作 ID，空间内唯一标识该接口")
    name: str = Field(..., description="接口名称")
    path: str = Field(..., description="接口路径，含路径参数占位符")
    method: str = Field(..., description="HTTP 方法")
    tags: str = Field(default="[]", description="标签，JSON 数组字符串")
    summary: str | None = Field(default="", description="接口摘要")
    description: str | None = Field(default="", description="接口描述")
    params: str | None = Field(default="{}", description="请求参数定义，JSON 对象字符串")
    headers: str | None = Field(default="{}", description="请求头定义，JSON 对象字符串")
    body: str | None = Field(default="{}", description="请求体定义，JSON 对象字符串")
    responses: str = Field(default="[]", description="响应定义，JSON 数组字符串")
    security: str = Field(default="[]", description="接口级认证方案，JSON 数组字符串")
    content_type: str = Field(default="application/json", description="请求体 Content-Type")
    deprecated: int = Field(default=0, description="是否已废弃：0-正常，1-已废弃")
    status: int = Field(default=1, description="状态：1-启用，2-禁用，3-已删除，4-已废弃")


# ==================== 创建 Schema ====================


class EndpointCreate(EndpointBase):
    """创建接口请求体。"""

    space_id: int | None = Field(default=None, description="所属空间 ID")

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
    """更新接口请求体，所有字段可选。"""

    operation_id: str | None = Field(default=None, description="操作 ID")
    name: str | None = Field(default=None, description="接口名称")
    path: str | None = Field(default=None, description="接口路径")
    method: HttpMethod | None = Field(default=None, description="HTTP 方法")
    tags: list[str] | None = Field(default=None, description="标签列表")
    summary: str | None = Field(default=None, description="接口摘要")
    description: str | None = Field(default=None, description="接口描述")
    params: dict | None = Field(default=None, description="请求参数定义")
    headers: dict | None = Field(default=None, description="请求头定义")
    body: dict | None = Field(default=None, description="请求体定义")
    responses: list | None = Field(default=None, description="响应定义")
    security: list | None = Field(default=None, description="接口级认证方案")
    content_type: str | None = Field(default=None, description="请求体 Content-Type")
    deprecated: int | None = Field(default=None, description="是否已废弃：0-正常，1-已废弃")
    status: int | None = Field(default=None, description="状态：1-启用，2-禁用，3-已删除，4-已废弃")

    @field_validator("tags", "params", "headers", "body", "responses", "security", mode="before")
    @classmethod
    def parse_json_fields(cls, v):
        """把以 JSON 字符串传入的结构字段解析为 Python 对象。

        Args:
            v: 字段原值，可能是 JSON 字符串或已解析对象

        Returns:
            解析后的对象；无法解析时为 None，非字符串原样返回
        """
        return parse_json_field(v)


# ==================== 响应 Schema ====================


class EndpointResponse(EndpointBase):
    """接口响应体。"""

    id: int = Field(..., description="接口 ID")
    space_id: int = Field(..., description="所属空间 ID")
    version: int = Field(default=1, description="定义版本号，每次变更递增")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class EndpointDetail(EndpointResponse):
    """接口详情响应，附带关联用例数。"""

    test_case_count: int | None = Field(default=0, description="关联测试用例数量")

    model_config = {"from_attributes": True}


# ==================== 列表/分页 Schema ====================


class EndpointListResponse(PaginatedResponse[EndpointResponse]):
    """接口列表响应。"""


class EndpointQuery(BaseModel):
    """接口查询参数。"""

    space_id: int | None = Field(default=None, description="空间 ID 筛选")
    method: HttpMethod | None = Field(default=None, description="HTTP 方法筛选")
    status: int | None = Field(default=None, description="状态筛选")
    tags: str | None = Field(default=None, description="标签筛选")
    keyword: str | None = Field(default=None, description="关键字，匹配名称、路径或描述")
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页记录数，1-100")


# ==================== 批量操作 Schema ====================


class EndpointBatchDelete(BatchDeleteRequest):
    """批量删除接口请求体。"""


class EndpointBatchUpdateStatus(BatchUpdateStatusRequest):
    """批量更新接口状态请求体。"""
