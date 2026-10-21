"""通用 Schema 与共享校验逻辑。

集中定义分页响应、批量操作请求，以及各实体 Schema 复用的字段校验函数，
避免在各实体 Schema 文件中重复相同结构与逻辑。
"""

import json
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """通用分页响应。

    各实体的 ``*ListResponse`` 通过 ``PaginatedResponse[XxxResponse]`` 复用此结构。
    """

    items: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")


class BatchDeleteRequest(BaseModel):
    """通用批量删除请求。"""

    ids: list[int] = Field(..., min_length=1, description="ID 列表")


class BatchUpdateStatusRequest(BaseModel):
    """通用批量更新状态请求。"""

    ids: list[int] = Field(..., min_length=1, description="ID 列表")
    status: int = Field(..., description="目标状态")


def strip_trailing_slash(value: Any) -> Any:
    """去除字符串末尾斜杠，保持 URL 统一格式（非字符串原样返回）。"""
    if isinstance(value, str):
        return value.rstrip("/")
    return value


def parse_json_field(value: Any) -> Any:
    """将 JSON 字符串解析为 Python 对象；解析失败返回 None，非字符串原样返回。"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return value
