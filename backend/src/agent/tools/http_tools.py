"""HTTP 请求工具（带环境闸门与 base_url 拼接）。

两道保护：``is_production`` 环境直接拒绝请求；完整 URL 的域名必须与环境
base_url 一致，避免被当作 SSRF 跳板。
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any
from urllib.parse import urlparse

from langchain_core.tools import BaseTool, tool
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.data.services import EnvironmentService
from src.utils.http.request import HttpRequest
from src.utils.json_utils import safe_json_loads

logger = get_logger(__name__)

SessionScope = Callable[[], AbstractContextManager[Session]]

#: 请求体的编码方式，见 ``send_request`` 的 ``body_type`` 说明
BODY_TYPES = ("auto", "json", "form", "raw")

#: 形如 ``k=v&k2=v2`` 的表单原文，用于 auto 模式识别
_FORM_BODY_RE = re.compile(r"^[^=&\s]+=[^&]*(?:&[^=&\s]+=[^&]*)*$")


def make_http_tools(
    space_id: int | str,
    environment_id: int | None = None,
    session_scope: SessionScope | None = None,
) -> list[BaseTool]:
    """构造 HTTP 请求工具集（绑定空间与环境）。

    Args:
        space_id: 空间 ID，环境列表按它查询
        environment_id: 默认测试环境 ID，None 表示未指定
        session_scope: 数据库会话作用域工厂；None 时使用全局数据库管理器

    Returns:
        工具列表：``list_environments``、``send_request``
    """
    scope = session_scope or _default_session_scope()

    @tool
    def list_environments() -> str:
        """列出当前空间配置的测试环境（名称、base_url、是否生产环境）。

        发请求前用于确认目标环境。
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
        headers: str | dict[str, Any] = "{}",
        body: str | dict[str, Any] | list[Any] = "",
        params: str | dict[str, Any] = "{}",
        timeout: int = 30,
        body_type: str = "auto",
    ) -> str:
        """发送 HTTP 请求并返回响应摘要（状态码、耗时、响应头、响应体）。

        副作用：向被测服务发起真实网络请求；生产环境会被拦截。

        path 可传相对路径（如 "/api/v1/login"，会拼上当前环境的 base_url），
        也可传完整 URL（必须与当前环境同域）。

        Args:
            path: 接口路径或完整 URL
            method: GET / POST / PUT / DELETE / PATCH，默认 GET
            headers: 请求头，JSON 对象文本或对象；非 ASCII 值按 UTF-8 字节发送
            body: 请求体。JSON 接口可给对象或 JSON 文本；表单给原文（如 'user=a&pwd=b'）；
                XML / 纯文本也给原文
            params: 查询参数，JSON 对象文本或对象，如 {"page": 1}
            timeout: 超时秒数，默认 30
            body_type: 请求体编码方式，默认 auto。
                auto —— 严格合法的 JSON 按 JSON 发；否则按原文发（识别为表单时自动带
                        x-www-form-urlencoded 头，其余带 text/plain）
                json —— 强制按 JSON 解析，非法 JSON 直接报错
                form —— 按 application/x-www-form-urlencoded 发；body 是 JSON 对象时自动编码
                raw  —— 原样逐字节发送，不解析也不修复；用于测非法 JSON、畸形 XML、
                        越界字段等脏数据
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

        return _do_request(url, method, headers, body, params, timeout, environment, body_type)

    return [list_environments, send_request]


# ---------------------------------------------------------------------------
# 内部
# ---------------------------------------------------------------------------


def _load_environment(scope: SessionScope, environment_id: int | None):
    """按 ID 载入测试环境；未指定时返回 None。"""
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
    headers: Any,
    body: Any,
    params: Any,
    timeout: int,
    environment,
    body_type: str = "auto",
) -> str:
    """发送请求，异常一律转成可读的 JSON 错误。"""
    upper = (method or "GET").upper()
    if upper not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
        return json.dumps({"error": f"不支持的 HTTP 方法: {method}"}, ensure_ascii=False)

    headers_dict, headers_error = _parse_mapping(headers, "headers")
    if headers_error:
        return json.dumps({"error": headers_error}, ensure_ascii=False)

    params_dict, params_error = _parse_mapping(params, "params")
    if params_error:
        return json.dumps({"error": params_error}, ensure_ascii=False)

    payload, prepare_error = _prepare_body(body, body_type, headers_dict)
    if prepare_error:
        return json.dumps({"error": prepare_error}, ensure_ascii=False)

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
        kwargs.update(payload)

        response = getattr(client, upper.lower())(endpoint, **kwargs)
        if response is None:
            return json.dumps({"error": "请求失败，无响应"}, ensure_ascii=False)

        try:
            resp_body: Any = response.json()
        except ValueError:
            resp_body = response.text

        response_headers = {k: v for k, v in response.headers.items() if k.lower() != "set-cookie"}

        logger.info(f"向{url}发送请求，"
                    f"\n请求方法：{method}，"
                    f"\n请求头：{headers}，"
                    f"\n请求参数：{params}，"
                    f"\n请求体：{body},"
                    f"\n超时时间：{timeout},"
                    f"\n响应头：{response_headers}"
                    f"\n响应体：{resp_body}")

        # 不做长度截断：截断由下游按用途分层（给模型 8000 字符、落库 2MB），
        # 工具层再截一次会让完整留痕拿不到全量；set-cookie 必须剔除，它是凭证。
        return json.dumps(
            {
                "status_code": response.status_code,
                "response_time_ms": round(response.elapsed.total_seconds() * 1000, 2),
                "headers": response_headers,
                "body": resp_body,
                "env": environment.name if environment is not None else "",
                "url": url,
            },
            ensure_ascii=False,
            default=str,
        )
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


def _parse_mapping(raw: Any, name: str) -> tuple[dict[str, Any], str | None]:
    """解析 headers / params 这类必须是 JSON 对象的入参。

    允许 ``json_repair`` 兜底修复少引号、单引号等小毛病，但结果必须是 dict：
    ``safe_json_loads('Bearer abc', {})`` 会静默退化为 ``{}``，导致鉴权头丢失。
    """
    if isinstance(raw, dict):
        return raw, None

    text = (raw or "").strip() if isinstance(raw, str) else ""
    if not text:
        return {}, None

    ok, parsed = _strict_json(text)
    if not ok:
        parsed = safe_json_loads(text, None)
    if isinstance(parsed, dict):
        return parsed, None
    return {}, f'{name} 必须是 JSON 对象（如 {{"k": "v"}}），收到: {raw}'


def _prepare_body(body: Any, body_type: str, headers: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """把模型给的 body 转成 requests 的 ``json=`` / ``data=`` 参数。

    不使用 ``safe_json_loads``：它的修复兜底会把表单原文转成空串，改变实际发出的
    字节。请求体只做严格解析或原样发送。

    Args:
        body: 请求体，字符串原文或 JSON 对象/数组
        body_type: ``auto`` / ``json`` / ``form`` / ``raw``
        headers: 请求头，函数内按需要写入 ``Content-Type``

    Returns:
        ``(kwargs 片段, 错误文案)``；错误文案非空时不应发请求。
    """
    kind = (body_type or "auto").strip().lower()
    if kind not in BODY_TYPES:
        return {}, f"不支持的 body_type: {body_type}，可选 {list(BODY_TYPES)}"

    # 模型直接把 body 写成 JSON 对象/数组：按 JSON 语义处理
    if isinstance(body, (dict, list)):
        if kind == "form":
            if not isinstance(body, dict):
                return {}, "body_type=form 时 body 只能是对象或表单原文"
            _set_header(headers, "Content-Type", "application/x-www-form-urlencoded")
            return {"data": body}, None
        if kind == "raw":
            _set_header(headers, "Content-Type", "application/json")
            return {"data": json.dumps(body, ensure_ascii=False).encode("utf-8")}, None
        return {"json": body}, None

    raw = body if isinstance(body, str) else ("" if body is None else str(body))
    if not raw.strip():
        return {}, None

    content_type = _get_header(headers, "content-type")
    strict_ok, parsed = _strict_json(raw)

    if kind == "json":
        if not strict_ok:
            return {}, (
                "body 不是合法 JSON，无法按 body_type=json 发送。"
                "如果就是要测非法 JSON 报文，请改用 body_type=raw 原样发送。"
            )
        return {"json": parsed}, None

    if kind == "form":
        _set_header(headers, "Content-Type", "application/x-www-form-urlencoded")
        if strict_ok and isinstance(parsed, dict):
            return {"data": parsed}, None
        return {"data": raw.encode("utf-8")}, None

    if kind == "raw":
        if not content_type:
            # 服务端按 Content-Type 决定是否走 JSON 解析；默认 text/plain 会先返回 415
            looks_json = raw.lstrip()[:1] in {"{", "["}
            _set_header(
                headers,
                "Content-Type",
                "application/json" if looks_json else "text/plain; charset=utf-8",
            )
        return {"data": raw.encode("utf-8")}, None

    # ---- auto ----
    if strict_ok:
        return {"json": parsed}, None

    if raw.lstrip()[:1] in {"{", "["}:
        return {}, (
            "body 看着像 JSON 但不合法（可能有多余逗号、缺引号、单引号等）。"
            "系统不会替你修复——要测「非法 JSON 被服务端拒绝」请显式传 body_type=raw。"
        )

    if content_type is None and _FORM_BODY_RE.match(raw.strip()):
        _set_header(headers, "Content-Type", "application/x-www-form-urlencoded")
    elif content_type is None:
        _set_header(headers, "Content-Type", "text/plain; charset=utf-8")
    return {"data": raw.encode("utf-8")}, None


def _strict_json(text: str) -> tuple[bool, Any]:
    """只做标准 ``json.loads``，不修复。"""
    try:
        return True, json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return False, None


def _get_header(headers: dict[str, Any], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return None if value is None else str(value)
    return None


def _set_header(headers: dict[str, Any], name: str, value: str) -> None:
    """大小写不敏感地写入请求头（避免与模型已给的同名头重复）。"""
    target = name.lower()
    for key in list(headers.keys()):
        if str(key).lower() == target:
            headers.pop(key)
    headers[name] = value


def _default_session_scope() -> SessionScope:
    """返回使用全局数据库管理器的会话作用域工厂。"""

    def _scope() -> AbstractContextManager[Session]:
        from src.core.database.database_manager import get_db_manager

        return get_db_manager().get_session()

    return _scope
