"""结构化数据查询工具：空间、接口清单、接口详情。

``space_id`` 由运行时从会话上下文注入闭包，不出现在工具参数中；
``search_space`` 是唯一跨空间的工具，语义即按名称查找空间。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from langchain_core.tools import BaseTool, tool
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.data.services import EndpointService, SpaceService
from src.utils.json_utils import as_object

logger = get_logger(__name__)

# 单个接口详情返回的字段数量上限，避免超长 schema 撑爆上下文
_MAX_SCHEMA_FIELDS = 40

SessionScope = Callable[[], AbstractContextManager[Session]]


def make_db_tools(space_id: int | str, session_scope: SessionScope | None = None) -> list[BaseTool]:
    """构造绑定到某个空间的接口查询工具。

    Args:
        space_id: 空间 ID，固定注入到工具闭包
        session_scope: 数据库会话作用域工厂；None 时使用全局数据库管理器

    Returns:
        工具列表：``get_space_endpoints``、``get_endpoint_detail_by_id``
    """
    scope = session_scope or _default_session_scope()

    @tool
    def get_space_endpoints() -> str:
        """获取当前空间下所有启用的 API 接口清单。

        返回 JSON 数组，每项含 id、name、path、method、summary、tags、response_summary。
        response_summary 是成功响应的顶层字段摘要，用于判断接口间的数据依赖。
        """
        with scope() as session:
            endpoints = EndpointService(session).list_active(int(space_id))

        payload = [
            {
                "id": ep.id,
                "name": ep.name,
                "path": ep.path,
                "method": ep.method,
                "summary": ep.summary or "",
                "tags": as_object(ep.tags),
                "response_summary": _build_response_summary(ep.responses),
            }
            for ep in endpoints
        ]
        return json.dumps(payload, ensure_ascii=False)

    @tool
    def get_endpoint_detail_by_id(endpoint_id: int) -> str:
        """获取当前空间下某个接口的完整定义。

        返回 name、path、method、summary、description、content_type、params（请求参数）、
        body（请求体 schema）、responses（各状态码结构摘要）、security（鉴权要求）、
        deprecated。接口不存在时返回带 error 字段的 JSON 对象。

        Args:
            endpoint_id: 接口 ID，取自 ``get_space_endpoints`` 的结果
        """
        with scope() as session:
            matches = EndpointService(session).get_active_by_ids([endpoint_id])

        endpoint = next((ep for ep in matches if ep.space_id == int(space_id)), None)
        if endpoint is None:
            logger.warning("接口不存在", space_id=str(space_id), endpoint_id=str(endpoint_id))
            return json.dumps(
                {
                    "error": f"当前空间下不存在 ID 为 {endpoint_id} 的启用接口，"
                    "请先用 get_space_endpoints 确认清单"
                },
                ensure_ascii=False,
            )

        detail: dict[str, Any] = {
            "id": endpoint.id,
            "name": endpoint.name,
            "path": endpoint.path,
            "method": endpoint.method,
            "summary": endpoint.summary or "",
            "description": endpoint.description or "",
            "content_type": endpoint.content_type,
            "tags": as_object(endpoint.tags),
            "params": as_object(endpoint.params),
            "body": as_object(endpoint.body),
            "responses": _build_response_digest(endpoint.responses),
            "security": as_object(endpoint.security),
            "deprecated": bool(endpoint.deprecated),
        }
        return json.dumps(detail, ensure_ascii=False)

    return [get_space_endpoints, get_endpoint_detail_by_id]


@tool
def search_space(keyword: str = "") -> str:
    """按名称搜索测试空间（跨空间，不限于当前空间）。

    关键字为空时返回最近的若干空间。

    Args:
        keyword: 空间名称关键字，支持模糊匹配
    """
    with _default_session_scope()() as session:  # noqa: SIM117
        service = SpaceService(session)
        results, _ = service.list_spaces(keyword or None, None, 1, 20)
        spaces = [
            {"id": space.id, "name": space.name, "description": space.description}
            for space in results
        ]
    return json.dumps(spaces, ensure_ascii=False)


# ---------------------------------------------------------------------------
# schema 摘要
# ---------------------------------------------------------------------------


def _build_response_summary(responses_json: str) -> str:
    """从 responses JSON 中提取成功响应的 schema 摘要（顶层属性名 + 类型）。"""
    try:
        responses = json.loads(responses_json) if responses_json else []
    except (json.JSONDecodeError, TypeError):
        return ""

    if not isinstance(responses, list) or not responses:
        return ""

    for resp in responses:
        if not isinstance(resp, dict):
            continue
        if not str(resp.get("status_code", "")).startswith("2"):
            continue

        for media_data in (resp.get("content") or {}).values():
            schema = (media_data or {}).get("schema") or {}
            properties = schema.get("properties") or {}
            if properties:
                fields = [f"{name}({prop.get('type', 'object')})" for name, prop in list(properties.items())[:10]]
                return ", ".join(fields)
            schema_type = (media_data or {}).get("type") or schema.get("type")
            if schema_type:
                return str(schema_type)
    return ""


def _build_response_digest(responses_json: str) -> list[dict[str, Any]]:
    """把 responses 压缩为「状态码 + 描述 + 顶层字段」。

    完整 schema 通常有数千 token，直接注入成本高且淹没关键信息。
    """
    try:
        responses = json.loads(responses_json) if responses_json else []
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(responses, list):
        return []

    digest: list[dict[str, Any]] = []
    for resp in responses:
        if not isinstance(resp, dict):
            continue
        entry: dict[str, Any] = {
            "status_code": resp.get("status_code", ""),
            "description": resp.get("description", ""),
            "fields": [],
        }
        for media_data in (resp.get("content") or {}).values():
            schema = (media_data or {}).get("schema") or {}
            properties = schema.get("properties") or {}
            required = set(schema.get("required") or [])
            for name, prop in list(properties.items())[:_MAX_SCHEMA_FIELDS]:
                if not isinstance(prop, dict):
                    continue
                entry["fields"].append(
                    {"name": name, "type": prop.get("type", "object"), "required": name in required}
                )
            if entry["fields"]:
                break
        digest.append(entry)
    return digest


def _default_session_scope() -> SessionScope:
    """返回使用全局数据库管理器的会话作用域工厂。"""

    def _scope() -> AbstractContextManager[Session]:
        from src.core.database.database_manager import get_db_manager

        return get_db_manager().get_session()

    return _scope
