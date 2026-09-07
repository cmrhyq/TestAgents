"""Skill 校验器注册表与内置校验器。

所有校验器签名统一为 ``fn(data, spec, context) -> list[ValidationError]``，
**绝不抛异常**，只返回结构化错误，供 runner 做重试/降级决策。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.graph.skill.base import ValidationSpec

# ---------------------------------------------------------------
# 错误对象与注册表
# ---------------------------------------------------------------


@dataclass
class ValidationError:
    """单条校验错误。"""

    field: str | None
    message: str
    value: Any = None

    def to_dict(self) -> dict:
        return {"field": self.field, "message": self.message}


ValidatorFn = Callable[[Any, "ValidationSpec", dict | None], list["ValidationError"]]

VALIDATORS: dict[str, ValidatorFn] = {}


def register_validator(name: str):
    """注册校验器到全局注册表。"""

    def decorator(fn):
        VALIDATORS[name] = fn
        return fn

    return decorator


def run_validations(
    data: Any,
    spec: ValidationSpec | None,
    context: dict | None = None,
) -> list[ValidationError]:
    """按 validation 规格执行校验。

    - output_type=list：校验顶层为 list
    - output_type=object：校验顶层为 dict + 必填字段 + 字段规则
    - 随后执行 custom_validators（引用 VALIDATORS 中的名字）
    """
    if spec is None:
        return []

    errors: list[ValidationError] = []

    if spec.output_type == "list":
        errors.extend(validate_list(data, spec, context))
    else:
        errors.extend(validate_json_object(data, spec, context))
        errors.extend(validate_required_fields(data, spec, context))
        errors.extend(validate_field_rules(data, spec, context))

    for name in spec.custom_validators:
        validator = VALIDATORS.get(name)
        if validator is None:
            errors.append(ValidationError(field=None, message=f"未知校验器: {name}", value=name))
            continue
        errors.extend(validator(data, spec, context))

    return errors


# ---------------------------------------------------------------
# 基础校验器
# ---------------------------------------------------------------


@register_validator("validate_json_object")
def validate_json_object(data: Any, spec: ValidationSpec, context: dict | None = None) -> list[ValidationError]:
    """顶层必须是 dict。"""
    if not isinstance(data, dict):
        return [ValidationError(field=None, message=f"输出必须是 JSON 对象，实际为 {type(data).__name__}", value=data)]
    return []


@register_validator("validate_list")
def validate_list(data: Any, spec: ValidationSpec, context: dict | None = None) -> list[ValidationError]:
    """list_key 子列表必须存在且为 list；未声明 list_key 时顶层必须是 list。"""
    if spec.list_key:
        if not isinstance(data, dict):
            return [
                ValidationError(field=spec.list_key, message=f"输出必须是 JSON 对象，实际为 {type(data).__name__}")
            ]
        value = data.get(spec.list_key)
        if not isinstance(value, list):
            return [ValidationError(field=spec.list_key, message=f"缺少列表字段 {spec.list_key}", value=value)]
        return []
    if not isinstance(data, list):
        return [ValidationError(field=None, message=f"输出必须是 JSON 数组，实际为 {type(data).__name__}")]
    return []


@register_validator("validate_required_fields")
def validate_required_fields(data: Any, spec: ValidationSpec, context: dict | None = None) -> list[ValidationError]:
    """顶层 required_fields 与 list_key 子项 item_required_fields 非空检查。"""
    errors: list[ValidationError] = []

    if spec.required_fields:
        if not isinstance(data, dict):
            return errors
        for field_name in spec.required_fields:
            if field_name not in data or _is_empty(data.get(field_name)):
                errors.append(ValidationError(field=field_name, message=f"必填字段缺失或为空: {field_name}"))

    if spec.item_required_fields and spec.list_key and isinstance(data, dict):
        items = data.get(spec.list_key, [])
        if isinstance(items, list):
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(ValidationError(field=f"{spec.list_key}[{idx}]", message="列表项必须是 JSON 对象"))
                    continue
                for field_name in spec.item_required_fields:
                    if field_name not in item or _is_empty(item.get(field_name)):
                        errors.append(
                            ValidationError(field=f"{spec.list_key}[{idx}].{field_name}", message=f"必填字段缺失或为空: {field_name}")
                        )

    return errors


@register_validator("validate_field_rules")
def validate_field_rules(data: Any, spec: ValidationSpec, context: dict | None = None) -> list[ValidationError]:
    """枚举/整数范围检查：作用于顶层对象与 list_key 子项中存在的字段。"""
    if not spec.field_rules:
        return []

    targets: list[tuple[str, dict]] = []
    if isinstance(data, dict):
        targets.append(("", data))
        if spec.list_key:
            items = data.get(spec.list_key, [])
            if isinstance(items, list):
                targets.extend((f"{spec.list_key}[{i}]", item) for i, item in enumerate(items) if isinstance(item, dict))

    errors: list[ValidationError] = []
    for location, obj in targets:
        for rule in spec.field_rules:
            if rule.field not in obj:
                continue
            value = obj[rule.field]
            if _is_empty(value):
                continue  # 缺失由 required_fields 负责
            errors.extend(_check_field_rule(rule.field, value, rule, location))
    return errors


def _check_field_rule(field_name: str, value: Any, rule, location: str) -> list[ValidationError]:
    """单条字段规则检查。"""
    qualified = f"{location}.{field_name}" if location else field_name

    if rule.type == "enum":
        if rule.values and value not in rule.values:
            return [
                ValidationError(
                    field=qualified,
                    message=f"字段 {field_name} 取值 {value!r} 不在允许范围 {rule.values}",
                    value=value,
                )
            ]
        return []

    if rule.type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            return [ValidationError(field=qualified, message=f"字段 {field_name} 必须是整数", value=value)]
        if rule.min is not None and value < rule.min:
            return [ValidationError(field=qualified, message=f"字段 {field_name} 不能小于 {rule.min}", value=value)]
        if rule.max is not None and value > rule.max:
            return [ValidationError(field=qualified, message=f"字段 {field_name} 不能大于 {rule.max}", value=value)]
        return []

    if rule.type == "list":
        if not isinstance(value, list):
            return [ValidationError(field=qualified, message=f"字段 {field_name} 必须是数组", value=value)]
        return []

    if rule.type == "bool":
        if not isinstance(value, bool):
            return [ValidationError(field=qualified, message=f"字段 {field_name} 必须是布尔值", value=value)]
        return []

    return []


# ---------------------------------------------------------------
# 领域校验器
# ---------------------------------------------------------------

# 断言规则语法（对齐 graph/executor/assertion_engine.py）
_ASSERT_OPERATORS = (
    "not_contains",
    "not_exists",
    "contains",
    "matches",
    "exists",
    ">=",
    "<=",
    "!=",
    "==",
    ">",
    "<",
)
# 二元运算符：<path> <op> <expected>；一元运算符：<path> exists|not_exists
_BINARY_OP_PATTERN = re.compile(r"^(.+?)\s+(?:==|!=|>=|<=|>|<|contains|not_contains|matches)\s+(.+)$")
_UNARY_OP_PATTERN = re.compile(r"^(.+?)\s+(exists|not_exists)$")
_ALLOWED_OPERATORS = frozenset(_ASSERT_OPERATORS)


def _collect_assert_rules(data: Any) -> list[tuple[str, Any]]:
    """从数据中收集所有 assert_rules 值（顶层或各列表项）。"""
    collected: list[tuple[str, Any]] = []

    def scan(obj: Any, location: str) -> None:
        if isinstance(obj, dict):
            if "assert_rules" in obj:
                collected.append((f"{location}.assert_rules" if location else "assert_rules", obj["assert_rules"]))
            for key, value in obj.items():
                if key != "assert_rules":
                    scan(value, f"{location}.{key}" if location else str(key))
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                scan(item, f"{location}[{idx}]")

    scan(data, "")
    return collected


@register_validator("validate_assert_rules_syntax")
def validate_assert_rules_syntax(data: Any, spec: ValidationSpec, context: dict | None = None) -> list[ValidationError]:
    """校验断言规则语法（对齐 assertion_engine：path + 运算符 + 期望值）。"""
    errors: list[ValidationError] = []
    for location, rules in _collect_assert_rules(data):
        if not isinstance(rules, list):
            errors.append(ValidationError(field=location, message="assert_rules 必须是字符串数组", value=rules))
            continue
        for idx, rule in enumerate(rules):
            if not isinstance(rule, str) or not rule.strip():
                errors.append(ValidationError(field=f"{location}[{idx}]", message="断言规则不能为空", value=rule))
                continue
            rule_str = rule.strip()
            if _BINARY_OP_PATTERN.match(rule_str) or _UNARY_OP_PATTERN.match(rule_str):
                continue
            errors.append(
                ValidationError(
                    field=f"{location}[{idx}]",
                    message=(
                        f"断言语法不合法: {rule_str!r}。应为 '<path> <运算符> <期望值>'，"
                        f"如 '$.code == 200' / 'status_code == 200' / '$.data.token exists'"
                    ),
                    value=rule_str,
                )
            )
    return errors


@register_validator("validate_cache_rules")
def validate_cache_rules(data: Any, spec: ValidationSpec, context: dict | None = None) -> list[ValidationError]:
    """校验 cache_rules 结构：extract 需 source_path+cache_key；inject 需 cache_key+target；首步 inject 应为空。"""
    errors: list[ValidationError] = []
    items: list[tuple[int, dict]] = []

    if isinstance(data, dict) and spec.list_key:
        raw_items = data.get(spec.list_key, [])
        if isinstance(raw_items, list):
            items = [(i, item) for i, item in enumerate(raw_items) if isinstance(item, dict)]

    for idx, item in items:
        cache_rules = item.get("cache_rules")
        if cache_rules is None:
            continue
        if not isinstance(cache_rules, dict):
            errors.append(ValidationError(field=f"test_cases[{idx}].cache_rules", message="cache_rules 必须是对象"))
            continue

        for rule in cache_rules.get("extract", []) or []:
            if not isinstance(rule, dict) or not rule.get("source_path") or not rule.get("cache_key"):
                errors.append(
                    ValidationError(
                        field=f"test_cases[{idx}].cache_rules.extract",
                        message="extract 规则必须包含 source_path 和 cache_key",
                        value=rule,
                    )
                )
        for rule in cache_rules.get("inject", []) or []:
            if not isinstance(rule, dict) or not rule.get("cache_key") or not rule.get("target"):
                errors.append(
                    ValidationError(
                        field=f"test_cases[{idx}].cache_rules.inject",
                        message="inject 规则必须包含 cache_key 和 target",
                        value=rule,
                    )
                )

    # 首步（step_order 最小）inject 应为空——无前置依赖
    ordered: list[tuple[int, dict]] = []
    for _, item in items:
        step = item.get("step_order")
        if isinstance(step, int):
            ordered.append((step, item))
    if ordered:
        first_step_item = min(ordered, key=lambda t: t[0])[1]
        inject_rules = first_step_item.get("cache_rules", {}).get("inject", []) if isinstance(
            first_step_item.get("cache_rules"), dict
        ) else []
        if inject_rules:
            errors.append(
                ValidationError(
                    field="test_cases[?].cache_rules.inject",
                    message="第一个步骤（最小 step_order）的 inject 应为空，无前置依赖",
                    value=inject_rules,
                )
            )

    return errors


@register_validator("validate_endpoint_ids")
def validate_endpoint_ids(data: Any, spec: ValidationSpec, context: dict | None = None) -> list[ValidationError]:
    """校验 endpoint_id 必须在 context['valid_endpoint_ids'] 内。"""
    valid_ids = (context or {}).get("valid_endpoint_ids")
    if valid_ids is None:
        return []  # 未提供上下文时跳过（由节点层处理未知 id）

    errors: list[ValidationError] = []
    valid_set = set(valid_ids)

    if isinstance(data, dict) and spec.list_key:
        items = data.get(spec.list_key, [])
        if isinstance(items, list):
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                endpoint_id = item.get("endpoint_id")
                if endpoint_id is not None and endpoint_id not in valid_set:
                    errors.append(
                        ValidationError(
                            field=f"test_cases[{idx}].endpoint_id",
                            message=f"endpoint_id {endpoint_id} 不在可用接口列表中",
                            value=endpoint_id,
                        )
                    )
    return errors


_RISK_LEVELS = ("none", "low", "medium", "high", "critical")
_VERDICT_ACTIONS = ("pass", "review", "block")


@register_validator("validate_risk_level")
def validate_risk_level(data: Any, spec: ValidationSpec, context: dict | None = None) -> list[ValidationError]:
    """校验安全审计结果：risk_level 枚举 + overall_verdict.action 枚举。"""
    errors: list[ValidationError] = []
    if not isinstance(data, dict):
        return errors

    security = data.get("security_analysis")
    if isinstance(security, dict):
        risk_level = security.get("risk_level")
        if risk_level not in _RISK_LEVELS:
            errors.append(
                ValidationError(
                    field="security_analysis.risk_level",
                    message=f"risk_level {risk_level!r} 不在允许范围 {list(_RISK_LEVELS)}",
                    value=risk_level,
                )
            )

    verdict = data.get("overall_verdict")
    if isinstance(verdict, dict):
        action = verdict.get("action")
        if action not in _VERDICT_ACTIONS:
            errors.append(
                ValidationError(
                    field="overall_verdict.action",
                    message=f"action {action!r} 不在允许范围 {list(_VERDICT_ACTIONS)}",
                    value=action,
                )
            )
    return errors


def _is_empty(value: Any) -> bool:
    """空值判断：None / 空白字符串 / 空列表 / 空字典。"""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False
