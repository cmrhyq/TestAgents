from pydantic import BaseModel, Field, field_validator

from src.data.constant.endpoint import TAG_FORBIDDEN_CHARS, TAG_MAX_COUNT, TAG_MAX_LENGTH
from src.data.enum.workflow import HttpMethod
from src.data.schemas.common import (
    BatchDeleteRequest,
    BatchUpdateStatusRequest,
    PaginatedResponse,
    parse_json_field,
)
from src.utils.json_utils import as_str_list

# ==================== 标签归一化 ====================


def _check_tags(tags: list[str]) -> list[str]:
    """校验并去重标签，写路径专用。

    去重不区分大小写，保留首次出现的写法：``["Auth", "auth"]`` 归一为
    ``["Auth"]``，避免同一语义的标签在筛选面板里出现两次。

    Args:
        tags: 已归一化的标签列表

    Returns:
        去重后的标签列表，顺序与原列表首次出现的顺序一致

    Raises:
        ValueError: 单个标签超长、含禁用字符，或数量超过上限
    """
    deduped: list[str] = []
    seen: set[str] = set()

    for tag in tags:
        if len(tag) > TAG_MAX_LENGTH:
            raise ValueError(f"单个标签不能超过 {TAG_MAX_LENGTH} 个字符：{tag[:20]}…")
        for char in TAG_FORBIDDEN_CHARS:
            if char in tag:
                raise ValueError(f'标签不能包含双引号或反斜杠：{tag}')
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(tag)

    if len(deduped) > TAG_MAX_COUNT:
        raise ValueError(f"单个接口最多 {TAG_MAX_COUNT} 个标签，当前 {len(deduped)} 个")

    return deduped


# ==================== 基础 Schema ====================


class EndpointBase(BaseModel):
    """接口基础字段。

    ``tags`` 对外一律是字符串数组：库内存 JSON 字符串，进出各进行一次转换。
    """

    operation_id: str = Field(..., description="操作 ID，空间内唯一标识该接口")
    name: str = Field(..., description="接口名称")
    path: str = Field(..., description="接口路径，含路径参数占位符")
    method: str = Field(..., description="HTTP 方法")
    tags: list[str] = Field(default_factory=list, description="标签列表")
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

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v):
        """把库内的 JSON 数组字符串或客户端传入的数组统一解析为列表。

        Args:
            v: 标签原值，可能是 JSON 字符串、数组或 None

        Returns:
            字符串列表；无法识别时为空列表
        """
        return as_str_list(v)


# ==================== 创建 Schema ====================


class EndpointCreate(EndpointBase):
    """创建接口请求体。

    ``params`` / ``headers`` / ``body`` / ``responses`` / ``security`` 需以 JSON 字符串
    提交（前端表单负责序列化），``tags`` 例外——直接传字符串数组。
    """

    space_id: int | None = Field(default=None, description="所属空间 ID")

    @field_validator("tags", mode="after")
    @classmethod
    def validate_tags(cls, v):
        """校验标签的数量、长度与字符。

        Args:
            v: 已归一化的标签列表

        Returns:
            去重后的标签列表

        Raises:
            ValueError: 违反任一约束，由 FastAPI 转为 HTTP 422
        """
        return _check_tags(v)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "space_id": 1,
                    "operation_id": "getUserById",
                    "name": "获取用户详情",
                    "path": "/api/v1/users/{id}",
                    "method": "GET",
                    "tags": ["用户管理", "只读"],
                    "summary": "根据ID获取用户信息",
                    "description": "通过用户ID查询用户详细信息",
                    "content_type": "application/json",
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
    # 结构类字段按 OpenAPI 实际形态放宽：参数/请求头为数组，请求体可为对象或数组
    params: dict | list | None = Field(default=None, description="请求参数定义，JSON 对象或数组")
    headers: dict | list | None = Field(default=None, description="请求头定义，JSON 对象或数组")
    body: dict | list | None = Field(default=None, description="请求体定义，JSON 对象或数组")
    responses: dict | list | None = Field(default=None, description="响应定义，JSON 对象或数组")
    security: dict | list | None = Field(default=None, description="接口级认证方案，JSON 对象或数组")
    content_type: str | None = Field(default=None, description="请求体 Content-Type")
    deprecated: int | None = Field(default=None, description="是否已废弃：0-正常，1-已废弃")
    status: int | None = Field(default=None, description="状态：1-启用，2-禁用，3-已删除，4-已废弃")

    @field_validator("method", mode="before")
    @classmethod
    def upper_method(cls, v):
        """把 HTTP 方法先转大写再做枚举校验，兼容 ``post`` 这类小写写法。

        Args:
            v: 方法原值

        Returns:
            大写后的字符串，非字符串原样返回
        """
        return v.upper() if isinstance(v, str) else v

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v):
        """把客户端传入的 JSON 字符串或数组解析为列表，``None`` 表示不修改。

        Args:
            v: 标签原值

        Returns:
            字符串列表；``None`` 原样返回，使 ``exclude_unset`` 语义不受影响
        """
        return None if v is None else as_str_list(v)

    @field_validator("tags", mode="after")
    @classmethod
    def validate_tags(cls, v):
        """校验标签的数量、长度与字符。

        Args:
            v: 已归一化的标签列表或 ``None``

        Returns:
            去重后的标签列表；``None`` 原样返回

        Raises:
            ValueError: 违反任一约束，由 FastAPI 转为 HTTP 422
        """
        return None if v is None else _check_tags(v)

    @field_validator("params", "headers", "body", "responses", "security", mode="before")
    @classmethod
    def parse_json_fields(cls, v):
        """把以 JSON 字符串传入的结构字段解析为 Python 对象。

        Args:
            v: 字段原值，可能是 JSON 字符串或已解析对象

        Returns:
            解析后的对象；空字符串视为未填返回 None，非字符串原样返回

        Raises:
            ValueError: 字符串不是合法 JSON，交由 FastAPI 返回 422 并提示原因
        """
        if isinstance(v, str) and not v.strip():
            return None
        parsed = parse_json_field(v)
        if parsed is None and isinstance(v, str):
            raise ValueError("必须是合法 JSON 字符串")
        return parsed


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


class EndpointTagFacet(BaseModel):
    """标签聚合项：空间内的标签名与其下的接口数量。"""

    name: str = Field(..., description="标签名")
    count: int = Field(..., description="带该标签的接口数量")


# ==================== 批量操作 Schema ====================


class EndpointBatchDelete(BatchDeleteRequest):
    """批量删除接口请求体。"""


class EndpointBatchUpdateStatus(BatchUpdateStatusRequest):
    """批量更新接口状态请求体。"""
