"""HTTP 请求工具（带环境闸门与 base_url 解析）。

这是整个系统里**唯一会改动外部状态**的工具，所以有两道保护：

1. **生产环境闸门**：环境被标记 ``is_production`` 时直接拒绝。测试 Agent 最大的
   事故风险就是「AI 觉得应该验证一下删除接口，于是在生产上删了数据」。
2. **URL 白名单式拼接**：传相对路径时只能用当前环境的 base_url，不允许模型
   自己拼一个任意域名发请求（否则等于给它一个 SSRF 跳板）。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any
from urllib.parse import urlparse

from langchain_core.tools import BaseTool, tool
from sqlalchemy.orm import Session

from src.agent.tools.common import as_object
from src.core.logging import get_logger
from src.data.services import EnvironmentService
from src.utils.http.request import HttpRequest
from src.utils.json_utils import safe_json_loads

logger = get_logger(__name__)

SessionScope = Callable[[], AbstractContextManager[Session]]

# 响应体回填模型时的字符上限，防止一个大列表把上下文吃干
MAX_RESPONSE_CHARS = 8000


def make_http_tools(
    space_id: int | str,
    environment_id: int | None = None,
    session_scope: SessionScope | None = None,
) -> list[BaseTool]:
    """构造 HTTP 请求工具集（绑定空间与环境）。"""
    scope = session_scope or _default_session_scope()

    @tool
    def list_environments() -> str:
        """列出当前空间配置的测试环境（名称、base_url、是否生产环境）。

        发送请求前建议先看一眼，确认要打的是哪个环境。
        """
        with scope() as session:
            envs = EnvironmentService(session).list_by_space(int(space_id))
        return json.dumps(
            [
                {
                    "id": env.id,
                    "name": env.name,
                    "base_url": env.base_url,
                    "is_production": bool(env.is_production),
                    "is_default": env.is_default,
                }
                for env in envs
            ],
            ensure_ascii=False,
        )

    @tool
    def send_request(
        path: str,
        method: str = "GET",
        headers: str = "{}",
        body: str = "{}",
        params: str = "{}",
        timeout: int = 30,
    ) -> str:
        """发送 HTTP 请求并返回响应摘要（状态码、耗时、响应头、响应体）。

        path 可以传相对路径（如 "/api/v1/login"，会拼上当前环境的 base_url），
        也可以传完整 URL（必须与当前环境同域）。

        Args:
            path: 接口路径或完整 URL
            method: GET / POST / PUT / DELETE / PATCH，默认 GET
            headers: 请求头 JSON，如 {"Authorization": "Bearer xxx"}
            body: 请求体 JSON（POST/PUT/PATCH 用）
            params: 查询参数 JSON，如 {"page": 1}
            timeout: 超时秒数，默认 30
        """
        environment = _load_environment(scope, environment_id)

        if environment is not None and environment.is_production:
            return json.dumps(
                {
                    "error": (
                        f"目标环境「{environment.name}」被标记为生产环境，请求已被拦截。"
                        "请让用户确认切换到测试环境后再试，不要尝试其他变通方式。"
                    ),
                    "blocked": True,
                },
                ensure_ascii=False,
            )

        url, url_error = _build_url(path, environment)
        if url_error:
            return json.dumps({"error": url_error}, ensure_ascii=False)

        return _do_request(url, method, headers, body, params, timeout, environment)

    return [list_environments, send_request]


# ---------------------------------------------------------------------------
# 内部
# ---------------------------------------------------------------------------


def _load_environment(scope: SessionScope, environment_id: int | None):
    if environment_id is None:
        return None
    with scope() as session:
        return EnvironmentService(session).get_by_id(int(environment_id))


def _build_url(path: str, environment) -> tuple[str, str | None]:
    """把 path 拼成完整 URL；返回 (url, 错误文案)。"""
    raw = (path or "").strip()
    if not raw:
        return "", "path 不能为空"

    if raw.startswith(("http://", "https://")):
        if environment is not None and environment.base_url:
            allowed = urlparse(environment.base_url).netloc
            actual = urlparse(raw).netloc
            if allowed and actual and actual != allowed:
                return "", (
                    f"完整 URL 的域名({actual})与环境 base_url 的域名({allowed})不一致。"
                    "请只传相对路径，让系统按环境拼接。"
                )
        return raw, None

    if environment is None or not environment.base_url:
        return "", "未指定测试环境，无法拼接相对路径。请先通过界面上选择环境，或改传完整 URL。"

    base = environment.base_url.rstrip("/")
    suffix = raw if raw.startswith("/") else f"/{raw}"
    return f"{base}{suffix}", None


def _do_request(
    url: str,
    method: str,
    headers: str,
    body: str,
    params: str,
    timeout: int,
    environment,
) -> str:
    """真正发请求；异常一律转成可读的 JSON 错误。"""
    upper = (method or "GET").upper()
    if upper not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
        return json.dumps({"error": f"不支持的 HTTP 方法: {method}"}, ensure_ascii=False)

    headers_dict = safe_json_loads(headers, {}) or {}
    params_dict = safe_json_loads(params, {}) or {}
    body_obj = as_object(body)

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    endpoint = parsed.path + (f"?{parsed.query}" if parsed.query else "")

    client: HttpRequest | None = None
    try:
        client = HttpRequest(
            base_url=base_url,
            connect_timeout=timeout,
            read_timeout=timeout,
            verify_ssl=True,
        )
        kwargs: dict[str, Any] = {"headers": headers_dict, "enable_retry": False}
        if params_dict:
            kwargs["params"] = params_dict
        if upper in {"POST", "PUT", "PATCH"} and body_obj is not None:
            kwargs["json"] = body_obj

        response = getattr(client, upper.lower())(endpoint, **kwargs)
        if response is None:
            return json.dumps({"error": "请求失败，无响应"}, ensure_ascii=False)

        try:
            resp_body: Any = response.json()
        except ValueError:
            resp_body = response.text[:MAX_RESPONSE_CHARS]

        payload = json.dumps(
            {
                "status_code": response.status_code,
                "response_time_ms": round(response.elapsed.total_seconds() * 1000, 2),
                "headers": {k: v for k, v in response.headers.items() if k.lower() != "set-cookie"},
                "body": resp_body,
                "env": environment.name if environment is not None else "",
                "url": url,
            },
            ensure_ascii=False,
            default=str,
        )
        if len(payload) > MAX_RESPONSE_CHARS:
            truncated = json.dumps(
                {
                    "note": f"响应体过大，已截断至 {MAX_RESPONSE_CHARS} 字符",
                    "preview": payload[:MAX_RESPONSE_CHARS],
                },
                ensure_ascii=False,
            )
            return truncated
        return payload
    except Exception as exc:
        logger.error("HTTP 请求失败", url=url, error=str(exc))
        return json.dumps(
            {
                "error": f"请求异常: {exc}",
                "hint": "若是连接超时，先确认环境 base_url 可达；若是 401/403，先取鉴权 token",
            },
            ensure_ascii=False,
        )
    finally:
        if client is not None:
            client.close()


def _default_session_scope() -> SessionScope:
    def _scope() -> AbstractContextManager[Session]:
        from src.core.database.database_manager import get_db_manager

        return get_db_manager().get_session()

    return _scope
