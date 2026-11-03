"""通用 Schema 与共享校验逻辑。

集中定义分页响应、批量操作请求，以及各实体 Schema 复用的字段校验函数。
"""

import json
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """通用分页响应。

    各实体的 ``*ListResponse`` 通过 ``PaginatedResponse[XxxResponse]`` 复用此结构。
    """

    items: list[T] = Field(default_factory=list, description="当前页数据")
    total: int = Field(default=0, description="记录总数")
    page: int = Field(default=1, description="当前页码，从 1 开始")
    page_size: int = Field(default=20, description="每页记录数")


class BatchDeleteRequest(BaseModel):
    """通用批量删除请求。"""

    ids: list[int] = Field(..., min_length=1, description="待删除记录 ID，至少一个")


class BatchUpdateStatusRequest(BaseModel):
    """通用批量更新状态请求。"""

    ids: list[int] = Field(..., min_length=1, description="待更新记录 ID，至少一个")
    status: int = Field(..., description="目标状态值")


def strip_trailing_slash(value: Any) -> Any:
    """去除字符串末尾的斜杠；非字符串原样返回。

    Args:
        value: 待处理值，通常是基础地址

    Returns:
        去掉末尾斜杠的字符串，或原值
    """
    if isinstance(value, str):
        return value.rstrip("/")
    return value


def parse_json_field(value: Any) -> Any:
    """把 JSON 字符串解析为 Python 对象；非字符串原样返回。

    Args:
        value: 待解析值

    Returns:
        解析后的对象；字符串无法解析时返回 None
    """
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return value
