"""Agent 执行记录落库实现。

设计约束（每一条都来自具体故障场景）：

1. **绝不抛异常**：记录失败不能影响对话——照抄 ``llm_service._record_usage`` 的
   做法，任何异常只 ``logger.warning``。
2. **每次写库一个短事务**：生成器可能被随时中断，长 session 会变成「已关闭的
   session」或连接泄漏。
3. **计数在内存累加**，``finish`` 时一次 UPDATE 写出：避免每来一个工具就
   UPDATE 一次 ``agent_run``（写放大 + 锁竞争）。
4. **``finish`` 幂等**：正常路径走一遍、``finally`` 再兜一遍不会写两次。
5. **``run_id`` 本地先生成**：不依赖写库成功，DB 挂了也能把成本归因串起来。
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
from src.data.models.base import local_now
from src.utils.id import next_id
from src.utils.json_utils import safe_json_loads

logger = get_logger(__name__)

SessionScope = Callable[[], AbstractContextManager[Session]]

# ---------------------------------------------------------------------------
# 长度上限（统一按 UTF-8 字节判断，与 response_size_bytes 口径一致）
# ---------------------------------------------------------------------------
MAX_RESPONSE_BODY_BYTES = 2 * 1024 * 1024  # 2MB
MAX_REQUEST_BODY_BYTES = 256 * 1024
MAX_HEADERS_BYTES = 32 * 1024
MAX_ARGS_BYTES = 64 * 1024
MAX_PREVIEW_CHARS = 4_000  # 与 events.MAX_TOOL_RESULT_CHARS 对齐
MAX_ERROR_CHARS = 2_000
MAX_TITLE_CHARS = 200
MAX_URL_CHARS = 2_000
MAX_CALL_ID_CHARS = 128

HTTP_TOOL_NAME = "send_request"

#: 需要打码的请求/响应头（大小写不敏感）
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

#: 工具名 -> 分类。名字必须与 ``src/agent/tools/`` 里 ``@tool`` 的实际函数名一致，
#: 否则 ``v_tool_call_stats`` 按 tool_type 聚合时会出现一大坨 "other"。
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
    "render_report": "exec",
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

#: 前缀兜底：未来新增 ``memory_xxx`` / ``knowledge_xxx`` / ``skill_xxx`` 时自动归类
_PREFIX_TYPES = (
    ("memory_", "memory"),
    ("knowledge_", "knowledge"),
    ("skill_", "skill"),
)


class AgentRunRecorder:
    """把一轮执行写成 ``agent_run`` + ``agent_tool_call``。"""

    def __init__(self, session_scope: SessionScope | None = None) -> None:
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

    # ── 1) 本轮开始 ──────────────────────────────────────────────────────
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
        """创建执行记录，返回 ``run_id``；写库失败时返回 None（本轮不记录）。"""
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

    # ── 2) 工具调用 ──────────────────────────────────────────────────────
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
        """写入一条工具调用留痕。"""
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

    # ── 3) 本轮终态 ──────────────────────────────────────────────────────
    def finish(self, *, status: str, error_message: str = "") -> None:
        """收尾：写终态、统计与 LLM 成本。幂等。"""
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


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _default_scope() -> SessionScope:
    """默认从全局数据库管理器取会话（惰性，构造时不触发 DB 初始化）。"""

    def _scope() -> AbstractContextManager[Session]:
        from src.core.database.database_manager import get_db_manager

        return get_db_manager().get_session()

    return _scope


def _classify(name: str) -> str:
    """工具名 -> 分类。"""
    if name in _TOOL_TYPES:
        return _TOOL_TYPES[name]
    for prefix, type_name in _PREFIX_TYPES:
        if name.startswith(prefix):
            return type_name
    return "other"


def _extract_http(name: str, args: dict[str, Any], outcome: ToolOutcome) -> dict[str, Any]:
    """从 ``send_request`` 的入参 + 结果里拆出 HTTP 列；其他工具返回空字典。

    只能靠解析返回体拿结构化信息：LangChain 的同步 ``@tool`` 在线程池里执行，
    ``ContextVar`` / ``threading.local`` 都拿不回调用方上下文（线程是新的），
    「工具顺手把 exchange 塞进侧信道」这条路走不通。
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
        # ⚠️ 这两个列要存 **合法 JSON**：模型给的是 dict，直接 str() 
        # 写进去是 Python repr（单引号），前端 JSON.parse 会炸，
        # v_http_endpoint_stats 之类按 JSON 取值也读不出来。
        "request_params": _as_json_text(args.get("params"), MAX_HEADERS_BYTES),
        "request_body": _as_json_text(args.get("body"), MAX_REQUEST_BODY_BYTES),
        "response_headers": _mask_headers(_dumps(data.get("headers") or {})),
        "response_body": body_text,
        "response_body_truncated": 1 if truncated else 0,
        "response_size_bytes": size,
    }


def _mask_headers(raw: Any) -> str | None:
    """把敏感请求/响应头打码后序列化。

    库里存明文 token 等于把凭证泄漏进备份与日志，必须处理。
    """
    if raw is None:
        return None
    data = safe_json_loads(raw, None) if isinstance(raw, str) else raw
    if isinstance(data, str):
        data = safe_json_loads(data, None)
    if not isinstance(data, dict):
        # 解析不出来就整体打码：宁可丢信息也不存明文
        return _clip(str(raw), MAX_HEADERS_BYTES)

    masked = {
        key: ("***" if any(s in str(key).lower() for s in _SENSITIVE_HEADERS) else value)
        for key, value in data.items()
    }
    return _clip(_dumps(masked), MAX_HEADERS_BYTES)


def _as_json_text(raw: Any, limit: int) -> str:
    """把入参里的 dict/list 序列化成合法 JSON 文本；字符串按原样保留。

    直接用 ``str(dict)`` 得到的是 Python repr（单引号），前端 ``JSON.parse``
    会失败，视图里也没法当 JSON 取字段。
    """
    if raw is None or raw == "":
        return "{}"
    text = raw if isinstance(raw, str) else _dumps(raw)
    return _clip(text, limit)


def _cap_body(body: Any) -> tuple[str | None, bool, int]:
    """按字节截断响应体，返回 ``(落库文本, 是否截断, 原始字节数)``。"""
    if body is None:
        return None, False, 0
    raw = body if isinstance(body, str) else _dumps(body)
    encoded = raw.encode("utf-8", errors="replace")
    if len(encoded) <= MAX_RESPONSE_BODY_BYTES:
        return raw, False, len(encoded)
    return encoded[:MAX_RESPONSE_BODY_BYTES].decode("utf-8", errors="ignore"), True, len(encoded)


def _dumps(value: Any) -> str:
    """安全 JSON 序列化（``default=str`` 兜住不可序列化的值）。"""
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _clip(value: str, limit: int, *, chars: bool = False) -> str:
    """按字符或字节截断。

    Args:
        value: 原文
        limit: 上限
        chars: True 表示按字符计（标题、错误信息这类短字段），
            False 表示按 UTF-8 字节计（请求/响应体这类可能很大的字段）
    """
    if not value:
        return ""
    if chars:
        return value[:limit]
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return value
    return encoded[:limit].decode("utf-8", errors="ignore")
