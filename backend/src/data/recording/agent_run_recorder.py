"""Agent 执行记录落库，写入 ``agent_run`` 与 ``agent_tool_call``。

记录失败只记日志，绝不打断对话；每次写库使用独立短事务，因为生成器可能被随时中断。
计数在内存累加，``finish`` 一次性 UPDATE；``finish`` 幂等，``run_id`` 本地预生成以便归因。
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from time import perf_counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.agent.recording import RunRecorder, ToolOutcome
from src.core.logging import get_logger
from src.data.constant.agent import HTTP_TOOL_NAME
from src.data.models.base import local_now
from src.utils.id import next_id
from src.utils.json_utils import safe_json_loads

logger = get_logger(__name__)

SessionScope = Callable[[], AbstractContextManager[Session]]

# 长度上限，统一按 UTF-8 字节判断，与 ``response_size_bytes`` 口径一致
MAX_RESPONSE_BODY_BYTES = 2 * 1024 * 1024  # 2MB
MAX_REQUEST_BODY_BYTES = 256 * 1024
MAX_HEADERS_BYTES = 32 * 1024
MAX_ARGS_BYTES = 64 * 1024
MAX_PREVIEW_CHARS = 4_000  # 与 events.MAX_TOOL_RESULT_CHARS 对齐
MAX_ERROR_CHARS = 2_000
MAX_TITLE_CHARS = 200
MAX_URL_CHARS = 2_000
MAX_CALL_ID_CHARS = 128


#: 需要打码的请求/响应头，大小写不敏感
_SENSITIVE_HEADERS = (
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "api-key",
    "apikey",
    "secret",
    "password",
    "x-auth-token",
)

#: 工具名到分类的映射。键名须与 ``src/agent/tools/`` 中 ``@tool`` 函数名一致，
#: 否则 ``v_tool_call_stats`` 按 ``tool_type`` 聚合时会归入 ``other``
_TOOL_TYPES = {
    # http
    "send_request": "http",
    "list_environments": "http",
    # db
    "get_space_endpoints": "db",
    "get_endpoint_detail_by_id": "db",
    # search
    "search_space": "search",
    "search_endpoint": "search",
    # fs
    "read_file": "fs",
    "write_file": "fs",
    "list_directory": "fs",
    "delete_file": "fs",
    # exec
    "evaluate_assertions": "exec",
    "extract_jsonpath": "exec",
    # memory（工具名不带 memory_ 前缀，只能逐个列）
    "recall": "memory",
    "remember": "memory",
    "forget": "memory",
    # knowledge
    "knowledge_search": "knowledge",
    # skill
    "list_skills": "skill",
    "read_skill": "skill",
}

#: 前缀兜底：新增 ``memory_xxx`` / ``knowledge_xxx`` / ``skill_xxx`` 时自动归类
_PREFIX_TYPES = (
    ("memory_", "memory"),
    ("knowledge_", "knowledge"),
    ("skill_", "skill"),
)


class AgentRunRecorder:
    """把一轮执行写成 ``agent_run`` + ``agent_tool_call``。"""

    def __init__(self, session_scope: SessionScope | None = None) -> None:
        """初始化计数器与写库入口。

        构造时不触达数据库，会话在每次写库时按需获取。

        Args:
            session_scope: 会话上下文工厂；None 时使用全局数据库管理器
        """
        self._scope = session_scope or _default_scope()
        self.run_id: int | None = None

        self._started = perf_counter()
        self._seq = 0
        self._tool_calls = 0
        self._ok = 0
        self._errors = 0
        self._duration_sum = 0
        self._finished = False
        self._lock = threading.Lock()

    # 本轮开始
    def start(
        self,
        *,
        space_id: int,
        environment_id: int | None = None,
        conversation_id: int | None = None,
        mode: str = "agent",
        title: str = "",
        trigger_type: str = "chat",
    ) -> int | None:
        """创建状态为 ``running`` 的执行记录。

        ``run_id`` 在写库前本地生成，写库失败时该轮不落库，调用方按 None 处理。

        副作用：写库并提交；失败只记日志，不抛异常。

        Args:
            space_id: 空间主键
            environment_id: 环境主键
            conversation_id: 会话主键，0 或空归一为 None
            mode: 工作模式
            title: 记录标题，超长截断
            trigger_type: 触发来源

        Returns:
            新建记录的 ``run_id``；写库失败时返回 None
        """
        run_id = next_id()
        now = local_now()
        try:
            from src.data.models.agent_run import AgentRun

            with self._scope() as session:
                session.add(
                    AgentRun(
                        id=run_id,
                        space_id=int(space_id),
                        environment_id=environment_id,
                        # 0 是 ensure_conversation 的降级值，落库时归一为 None
                        conversation_id=int(conversation_id) if conversation_id else None,
                        title=_clip(title or "", MAX_TITLE_CHARS, chars=True),
                        mode=mode or "agent",
                        trigger_type=trigger_type or "chat",
                        status="running",
                        started_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
                session.commit()
        except Exception as exc:  # 落库失败不能带崩对话
            logger.warning("Agent 执行记录创建失败，本轮不落库: %s", exc)
            return None

        self.run_id = run_id
        self._started = perf_counter()
        logger.debug("Agent 执行记录已创建", run_id=run_id, space_id=space_id)
        return run_id

    # 工具调用
    def tool_call(
        self,
        *,
        step: int,
        seq: int,
        call_id: str,
        name: str,
        args: dict[str, Any],
        outcome: ToolOutcome,
        duration_ms: int,
    ) -> None:
        """写入一条工具调用留痕并累加内存计数。

        ``run_id`` 为空（本轮未落库）时直接返回。

        副作用：写库并提交；失败只记日志，不抛异常。

        Args:
            step: 所属的模型轮次
            seq: 轮次内的调用序号
            call_id: 模型侧的调用标识，超长截断
            name: 工具名，用于推断 ``tool_type``
            args: 工具入参，序列化后落库
            outcome: 调用结果，含状态、错误与文本输出
            duration_ms: 调用耗时
        """
        if self.run_id is None:
            return
        try:
            from src.data.models.agent_tool_call import AgentToolCall

            http_fields = _extract_http(name, args, outcome)
            with self._scope() as session:
                session.add(
                    AgentToolCall(
                        run_id=self.run_id,
                        step_index=int(step),
                        seq=int(seq),
                        call_id=_clip(call_id, MAX_CALL_ID_CHARS, chars=True),
                        tool_name=_clip(name, 128, chars=True),
                        tool_type=_classify(name),
                        args_json=_clip(_dumps(args), MAX_ARGS_BYTES),
                        ok=1 if outcome.ok else 0,
                        error_type=_clip(outcome.error_type, 128, chars=True),
                        error_message=_clip(outcome.error_message, MAX_ERROR_CHARS, chars=True),
                        result_preview=_clip(outcome.text, MAX_PREVIEW_CHARS, chars=True),
                        result_chars=len(outcome.text or ""),
                        duration_ms=int(duration_ms),
                        **http_fields,
                    )
                )
                session.commit()
            with self._lock:
                self._seq += 1
                self._tool_calls += 1
                self._duration_sum += int(duration_ms)
                if outcome.ok:
                    self._ok += 1
                else:
                    self._errors += 1
        except Exception as exc:
            logger.warning("工具调用留痕写入失败 tool=%s: %s", name, exc)

    # 本轮终态
    def finish(self, *, status: str, error_message: str = "") -> None:
        """写入终态、统计值与 LLM 成本汇总，幂等。

        正常路径与 ``finally`` 各调一次也只写一次。成本与 token 由 ``llm_log``
        的子查询聚合，需在调用前已完成用量落库。

        副作用：写库并提交；失败只记日志，不抛异常。

        Args:
            status: 终态取值
            error_message: 失败原因，超长截断
        """
        if self.run_id is None or self._finished:
            return
        self._finished = True

        now = local_now()
        duration_ms = int((perf_counter() - self._started) * 1000)
        with self._lock:
            calls = self._tool_calls
            ok = self._ok
            errors = self._errors
            avg = round(self._duration_sum / calls, 2) if calls else 0.0
        rate = round(ok / calls * 100, 2) if calls else 0.0

        try:
            with self._scope() as session:
                session.execute(
                    text(
                        "UPDATE agent_run SET "
                        "status=:status, finished_at=:fin, duration_ms=:dur, "
                        "tool_call_count=:calls, ok_count=:ok, error_count=:errors, "
                        "success_rate=:rate, avg_response_time=:avg, "
                        "error_message=:err, updated_at=:now, "
                        "llm_call_count=(SELECT COUNT(*) FROM llm_log WHERE run_id=:rid), "
                        "total_tokens=COALESCE((SELECT SUM(total_tokens) FROM llm_log WHERE run_id=:rid), 0), "
                        "cost_usd=COALESCE((SELECT SUM(cost_usd) FROM llm_log WHERE run_id=:rid), 0) "
                        "WHERE id=:rid"
                    ),
                    {
                        "status": status,
                        "fin": now,
                        "now": now,
                        "dur": duration_ms,
                        "calls": calls,
                        "ok": ok,
                        "errors": errors,
                        "rate": rate,
                        "avg": avg,
                        "err": _clip(error_message or "", MAX_ERROR_CHARS, chars=True),
                        "rid": self.run_id,
                    },
                )
                session.commit()
            logger.debug(
                "Agent 执行记录已收尾",
                run_id=self.run_id,
                status=status,
                tool_calls=calls,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            logger.warning("Agent 执行记录收尾失败 run_id=%s: %s", self.run_id, exc)


# 内部工具


def _default_scope() -> SessionScope:
    """返回默认会话工厂，惰性获取全局数据库管理器，构造时不触发初始化。

    Returns:
        可调用对象，每次调用返回一个会话上下文
    """

    def _scope() -> AbstractContextManager[Session]:
        from src.core.database.database_manager import get_db_manager

        return get_db_manager().get_session()

    return _scope


def _classify(name: str) -> str:
    """按映射表与名字前缀判定工具分类，未匹配时返回 ``other``。

    Args:
        name: 工具名

    Returns:
        分类标识
    """
    if name in _TOOL_TYPES:
        return _TOOL_TYPES[name]
    for prefix, type_name in _PREFIX_TYPES:
        if name.startswith(prefix):
            return type_name
    return "other"


def _extract_http(name: str, args: dict[str, Any], outcome: ToolOutcome) -> dict[str, Any]:
    """从 ``send_request`` 的入参与结果中拆出 HTTP 列，其他工具返回空字典。

    只能靠解析返回体取结构化信息：LangChain 的同步 ``@tool`` 在线程池中执行，
    ``ContextVar`` 与 ``threading.local`` 都拿不到调用方上下文。

    Args:
        name: 工具名
        args: 工具入参
        outcome: 调用结果，``text`` 为工具返回的 JSON 文本

    Returns:
        可直接展开为 ``AgentToolCall`` 字段的字典；非 HTTP 工具或返回体不可解析时为空
    """
    if name != HTTP_TOOL_NAME:
        return {}
    data = safe_json_loads(outcome.text, None)
    if not isinstance(data, dict) or "status_code" not in data and "error" not in data:
        return {}

    body = data.get("body")
    body_text = _dumps(body) if body is not None else None
    body_text, truncated, size = _cap_body(body_text)

    status_code = data.get("status_code")
    return {
        "http_method": _clip(str(args.get("method") or "GET").upper(), 16, chars=True),
        "http_url": _clip(str(data.get("url") or ""), MAX_URL_CHARS, chars=True) or None,
        "http_status_code": status_code if isinstance(status_code, int) else None,
        "request_headers": _mask_headers(args.get("headers")),
        # 这两列须为合法 JSON：模型传入的是 dict，``str()`` 会写成 Python repr，
        # 前端 JSON.parse 与视图按 JSON 取值都会失败
        "request_params": _as_json_text(args.get("params"), MAX_HEADERS_BYTES),
        "request_body": _as_json_text(args.get("body"), MAX_REQUEST_BODY_BYTES),
        "response_headers": _mask_headers(_dumps(data.get("headers") or {})),
        "response_body": body_text,
        "response_body_truncated": 1 if truncated else 0,
        "response_size_bytes": size,
    }


def _mask_headers(raw: Any) -> str | None:
    """按敏感头名单打码后序列化。

    库中存明文凭证会随备份与日志外泄，必须打码。

    Args:
        raw: 头部，可为 dict、JSON 字符串或 None

    Returns:
        打码后的 JSON 字符串；入参为 None 时返回 None；
        无法解析为字典时对整体打码后截断
    """
    if raw is None:
        return None
    data = safe_json_loads(raw, None) if isinstance(raw, str) else raw
    if isinstance(data, str):
        data = safe_json_loads(data, None)
    if not isinstance(data, dict):
        # 无法解析时整体打码，避免存明文
        return _clip(str(raw), MAX_HEADERS_BYTES)

    masked = {
        key: ("***" if any(s in str(key).lower() for s in _SENSITIVE_HEADERS) else value)
        for key, value in data.items()
    }
    return _clip(_dumps(masked), MAX_HEADERS_BYTES)


def _as_json_text(raw: Any, limit: int) -> str:
    """把 dict 或 list 序列化为合法 JSON 文本，字符串按原样保留。

    直接用 ``str(dict)`` 得到的是 Python repr，前端 ``JSON.parse`` 会失败，
    视图也无法按 JSON 取字段。

    Args:
        raw: 待序列化的值
        limit: 字节上限，超出截断

    Returns:
        JSON 文本；入参为 None 或空串时返回 ``{}``
    """
    if raw is None or raw == "":
        return "{}"
    text = raw if isinstance(raw, str) else _dumps(raw)
    return _clip(text, limit)


def _cap_body(body: Any) -> tuple[str | None, bool, int]:
    """按字节截断响应体，截断处可能丢失半个多字节字符。

    Args:
        body: 响应体，可为对象或字符串

    Returns:
        ``(落库文本, 是否截断, 原始字节数)``；入参为 None 时文本为 None
    """
    if body is None:
        return None, False, 0
    raw = body if isinstance(body, str) else _dumps(body)
    encoded = raw.encode("utf-8", errors="replace")
    if len(encoded) <= MAX_RESPONSE_BODY_BYTES:
        return raw, False, len(encoded)
    return encoded[:MAX_RESPONSE_BODY_BYTES].decode("utf-8", errors="ignore"), True, len(encoded)


def _dumps(value: Any) -> str:
    """JSON 序列化，不可序列化的值退化为 ``str``。

    Args:
        value: 待序列化的值

    Returns:
        JSON 文本；序列化失败时返回 ``str(value)``
    """
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _clip(value: str, limit: int, *, chars: bool = False) -> str:
    """按字符或 UTF-8 字节截断字符串。

    Args:
        value: 原文
        limit: 上限
        chars: 为 True 时按字符计，用于标题、错误信息等短字段；
            为 False 时按 UTF-8 字节计，用于请求体、响应体等长字段

    Returns:
        截断后的字符串；入参为空时返回空串
    """
    if not value:
        return ""
    if chars:
        return value[:limit]
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return value
    return encoded[:limit].decode("utf-8", errors="ignore")
