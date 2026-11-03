"""断言规则解析与评估。

规则形如 ``$.code == 200``、``$.data.token exists``、``$.message contains "x"``、
``status_code == 200``、``response_time < 3000``；实际值取自响应体 JSONPath、
HTTP 状态码或响应耗时（毫秒）。
"""

import re
from typing import Any

from src.core.logging import get_logger
from src.agent.tools.jsonpath import extract_jsonpath

logger = get_logger(__name__)

_OPERATORS_BY_LENGTH = [
    ("not_contains", "not_contains"),
    ("not_exists", "not_exists"),
    ("contains", "contains"),
    ("matches", "matches"),
    ("exists", "exists"),
    (">=", ">="),
    ("<=", "<="),
    ("!=", "!="),
    ("==", "=="),
    (">", ">"),
    ("<", "<"),
]


class AssertionEngine:
    """断言规则解析与评估引擎。"""

    def evaluate_all(
        self,
        rules: list[str],
        response_body: Any,
        status_code: int,
        response_time: float,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """评估所有断言规则。

        Args:
            rules: 断言规则字符串列表
            response_body: HTTP 响应体（已解析的 dict/list 或原始字符串）
            status_code: HTTP 状态码
            response_time: 响应时间（毫秒）

        Returns:
            ``(all_passed, details)``；details 为每条规则的评估结果
        """
        details: list[dict[str, Any]] = []
        all_passed = True

        for rule_str in rules:
            result = self._evaluate_single(rule_str, response_body, status_code, response_time)
            details.append(result)
            if not result["passed"]:
                all_passed = False

        failed_count = sum(1 for d in details if not d["passed"])
        if all_passed:
            logger.debug(f"断言全部通过，规则数: {len(rules)}", rule_count=len(rules))
        else:
            logger.debug(
                f"断言部分失败 - 总数: {len(rules)}, 失败: {failed_count}", total=len(rules), failed=failed_count
            )

        return all_passed, details

    def _evaluate_single(
        self,
        rule_str: str,
        response_body: Any,
        status_code: int,
        response_time: float,
    ) -> dict[str, Any]:
        """评估单条断言规则；解析异常被吞掉并记为未通过。"""
        try:
            path, operator, expected = self._parse_rule(rule_str)
            actual = self._resolve_value(path, response_body, status_code, response_time)
            passed = self._compare(actual, operator, expected)
            return {
                "rule": rule_str,
                "passed": passed,
                "actual": actual,
                "expected": expected,
                "operator": operator,
            }
        except Exception as e:
            logger.warning(f"断言评估异常: {rule_str}，错误: {e}", rule=rule_str, error=str(e))
            return {
                "rule": rule_str,
                "passed": False,
                "actual": None,
                "expected": None,
                "operator": "",
                "error": str(e),
            }

    def _parse_rule(self, rule_str: str) -> tuple[str, str, Any]:
        """解析断言规则字符串为 ``(path, operator, expected)``。

        Args:
            rule_str: 如 "$.code == 200" 或 "$.data.token exists"

        Returns:
            ``(path, operator, expected_value)``

        Raises:
            ValueError: 规则中找不到任何受支持的运算符
        """
        rule_str = rule_str.strip()

        for op_text, op_name in _OPERATORS_BY_LENGTH:
            if op_name in ("exists", "not_exists"):
                pattern = rf"^(.+?)\s+{op_text}\s*$"
                match = re.match(pattern, rule_str)
                if match:
                    return match.group(1).strip(), op_name, None
            else:
                separator = f" {op_text} "
                if separator in rule_str:
                    parts = rule_str.split(separator, 1)
                    path = parts[0].strip()
                    expected = self._parse_expected_value(parts[1].strip())
                    return path, op_name, expected

        raise ValueError(f"无法解析断言规则: {rule_str}")

    def _resolve_value(
        self,
        path: str,
        response_body: Any,
        status_code: int,
        response_time: float,
    ) -> Any:
        """根据 path 从响应数据中提取实际值。

        支持 ``$.xxx.yyy`` 与 ``$[0].xxx`` 形式的 JSONPath，以及 ``status_code``、
        ``response_time`` 两个保留路径。
        """
        if path == "status_code":
            return status_code
        if path == "response_time":
            return response_time

        if path.startswith("$."):
            return extract_jsonpath(response_body, path)

        if path.startswith("$["):
            return extract_jsonpath(response_body, path)

        return extract_jsonpath(response_body, f"$.{path}")

    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        """执行比较运算；未知运算符返回 False。"""
        if operator == "exists":
            return actual is not None
        if operator == "not_exists":
            return actual is None

        if operator == "==":
            return self._equal(actual, expected)
        if operator == "!=":
            return not self._equal(actual, expected)

        if operator == "contains":
            return self._contains(actual, expected)
        if operator == "not_contains":
            return not self._contains(actual, expected)

        if operator == "matches":
            if actual is None:
                return False
            try:
                return bool(re.search(str(expected), str(actual)))
            except re.error:
                return False

        if operator in (">", "<", ">=", "<="):
            return self._numeric_compare(actual, operator, expected)

        logger.warning(f"未知运算符: {operator}", operator=operator)
        return False

    @staticmethod
    def _equal(actual: Any, expected: Any) -> bool:
        """宽松等值比较：尝试数值比较后回退字符串比较。"""
        if actual == expected:
            return True
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return str(actual) == str(expected)

    @staticmethod
    def _contains(actual: Any, expected: Any) -> bool:
        """包含检查：支持字符串包含和列表包含。"""
        if actual is None:
            return False
        if isinstance(actual, str):
            return str(expected) in actual
        if isinstance(actual, list):
            return expected in actual
        return str(expected) in str(actual)

    @staticmethod
    def _numeric_compare(actual: Any, operator: str, expected: Any) -> bool:
        """数值比较。"""
        try:
            a = float(actual)
            b = float(expected)
        except (TypeError, ValueError):
            return False

        if operator == ">":
            return a > b
        if operator == "<":
            return a < b
        if operator == ">=":
            return a >= b
        if operator == "<=":
            return a <= b
        return False

    @staticmethod
    def _parse_expected_value(value_str: str) -> Any:
        """解析期望值字符串为 Python 对象。"""
        if not value_str:
            return ""

        if value_str.lower() in ("null", "none"):
            return None
        if value_str.lower() == "true":
            return True
        if value_str.lower() == "false":
            return False

        if (value_str.startswith('"') and value_str.endswith('"')) or (
            value_str.startswith("'") and value_str.endswith("'")
        ):
            return value_str[1:-1]

        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            return value_str
