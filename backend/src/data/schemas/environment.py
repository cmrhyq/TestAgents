from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.data.schemas.common import (
    BatchDeleteRequest,
    BatchUpdateStatusRequest,
    PaginatedResponse,
    parse_json_field,
    strip_trailing_slash,
)

# ==================== 基础 Schema ====================


class EnvironmentBase(BaseModel):
    """测试环境基础字段。"""

    name: str = Field(..., min_length=1, max_length=100, description="环境名称")
    base_url: str = Field(..., description="环境基础地址，不含末尾斜杠")
    description: str | None = Field(default="", description="环境描述")
    variables: str = Field(default="", description="环境变量，JSON 对象字符串")
    is_default: int = Field(default=1, description="是否默认环境：1-是，0-否")
    is_production: int = Field(default=0, description="是否生产环境：1-是，0-否；生产环境会拦截写请求")
    status: int = Field(default=1, description="状态：1-启用，2-禁用，3-已删除，4-已废弃")

    @field_validator("base_url", mode="before")
    @classmethod
    def validate_base_url(cls, v):
        """归一化基础地址，去掉末尾斜杠。

        Args:
            v: 基础地址原值

        Returns:
            去掉末尾斜杠的地址；非字符串原样返回
        """
        return strip_trailing_slash(v)


# ==================== 创建 Schema ====================


class EnvironmentCreate(EnvironmentBase):
    """创建环境请求体。"""

    space_id: int = Field(..., description="所属空间 ID")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "space_id": 1,
                    "name": "开发环境",
                    "base_url": "https://dev-api.example.com",
                    "description": "开发联调环境",
                    "variables": {"token": "dev_token_xxx", "timeout": 30, "debug": True},
                    "is_default": 0,
                    "status": 1,
                }
            ]
        }
    }


# ==================== 更新 Schema ====================


class EnvironmentUpdate(BaseModel):
    """更新环境请求体，所有字段可选。"""

    name: str | None = Field(default=None, min_length=1, max_length=100, description="环境名称")
    base_url: str | None = Field(default=None, description="环境基础地址，不含末尾斜杠")
    description: str | None = Field(default=None, description="环境描述")
    variables: dict[str, Any] | None = Field(default=None, description="环境变量键值对")
    is_default: int | None = Field(default=None, description="是否默认环境：1-是，0-否")
    is_production: int | None = Field(default=None, description="是否生产环境：1-是，0-否")
    status: int | None = Field(default=None, description="状态：1-启用，2-禁用，3-已删除，4-已废弃")

    @field_validator("base_url", mode="before")
    @classmethod
    def validate_base_url(cls, v):
        """归一化基础地址，去掉末尾斜杠。

        Args:
            v: 基础地址原值

        Returns:
            去掉末尾斜杠的地址；非字符串原样返回
        """
        return strip_trailing_slash(v)

    @field_validator("variables", mode="before")
    @classmethod
    def parse_variables(cls, v):
        """把 JSON 字符串形式的环境变量解析为字典。

        Args:
            v: 字段原值，可能是 JSON 字符串或已解析对象

        Returns:
            解析后的对象；无法解析时为 None，非字符串原样返回
        """
        return parse_json_field(v)


# ==================== 响应 Schema ====================


class EnvironmentResponse(EnvironmentBase):
    """环境响应体。"""

    id: int = Field(..., description="环境 ID")
    space_id: int = Field(..., description="所属空间 ID")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class EnvironmentDetail(EnvironmentResponse):
    """环境详情响应，附带统计信息。"""

    test_run_count: int | None = Field(default=0, description="使用该环境的执行记录数")

    model_config = {"from_attributes": True}


# ==================== 列表/分页 Schema ====================


class EnvironmentListResponse(PaginatedResponse[EnvironmentResponse]):
    """环境列表响应。"""


class EnvironmentQuery(BaseModel):
    """环境查询参数。"""

    space_id: int | None = Field(default=None, description="空间 ID 筛选")
    name: str | None = Field(default=None, description="环境名称，模糊匹配")
    is_default: int | None = Field(default=None, description="是否默认环境筛选")
    status: int | None = Field(default=None, description="状态筛选")
    keyword: str | None = Field(default=None, description="关键字，匹配名称或描述")
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页记录数，1-100")


# ==================== 批量操作 Schema ====================


class EnvironmentBatchDelete(BatchDeleteRequest):
    """批量删除环境请求体。"""


class EnvironmentBatchUpdateStatus(BatchUpdateStatusRequest):
    """批量更新环境状态请求体。"""
