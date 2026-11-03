"""执行域工具：断言求值与 JSONPath 取值。

纯逻辑、无 IO、无副作用，因此在所有模式下都可用。
"""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool, tool

from src.agent.tools.assertion_engine import AssertionEngine
from src.agent.tools.common import as_object
from src.agent.tools.jsonpath import extract_jsonpath as _extract_jsonpath
from src.core.logging import get_logger

logger = get_logger(__name__)

_engine = AssertionEngine()


def make_executor_tools() -> list[BaseTool]:
    """构造断言与 JSONPath 工具（无空间绑定）。

    Returns:
        工具列表：``evaluate_assertions``、``extract_jsonpath``
    """

    @tool
    def evaluate_assertions(
        rules: str,
        response_body: str,
        status_code: int = 0,
        response_time: float = 0.0,
    ) -> str:
        """评估断言规则，返回每条规则的通过情况。

        支持的语法：
        - `$.code == 200`            等值比较
        - `$.data.token exists`      字段存在性
        - `$.message contains "err"` 包含子串
        - `status_code == 200`       HTTP 状态码
        - `response_time < 3000`     响应时间（毫秒）

        Args:
            rules: 断言规则，多行文本或 JSON 数组，如 "$.code == 200\\n$.data.id exists"
            response_body: 响应体（JSON 字符串；非 JSON 文本也可直接传入）
            status_code: HTTP 状态码
            response_time: 响应耗时（毫秒）
        """
        rule_list = _parse_rules(rules)
        if not rule_list:
            return json.dumps({"error": "未提供有效的断言规则"}, ensure_ascii=False)

        try:
            body = as_object(response_body)
            all_passed, details = _engine.evaluate_all(rule_list, body, status_code, response_time)
        except Exception as exc:
            logger.error("断言评估失败", error=str(exc))
            return json.dumps({"all_passed": False, "error": str(exc)}, ensure_ascii=False)

        return json.dumps(
            {"all_passed": all_passed, "details": details},
            ensure_ascii=False,
            default=str,
        )

    @tool
    def extract_jsonpath(data: str, path: str) -> str:
        """按 JSONPath 从 JSON 里取值（支持 $.a.b.c 与 $.a[0].b）。

        Args:
            data: JSON 字符串
            path: JSONPath 表达式，如 "$.data.token"
        """
        try:
            result = _extract_jsonpath(as_object(data), path)
        except Exception as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False, default=str)

    return [evaluate_assertions, extract_jsonpath]


def _parse_rules(rules: str) -> list[str]:
    """把多行文本或 JSON 数组归一化为规则列表。"""
    raw = (rules or "").strip()
    if not raw:
        return []

    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(r).strip() for r in parsed if str(r).strip()]
        except json.JSONDecodeError:
            pass

    return [line.strip() for line in raw.splitlines() if line.strip()]
