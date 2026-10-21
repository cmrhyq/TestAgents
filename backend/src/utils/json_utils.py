"""JSON 解析公共工具。

统一空间内的 JSON 字段解析与 LLM 响应 JSON 提取逻辑：
- ``robust_json_loads`` / ``safe_json_loads``：带 ``json_repair`` 兜底的安全解析
- ``parse_llm_json_response`` / ``parse_llm_json_object``：从 LLM 文本中提取 JSON
"""

import json
import re
from typing import Any

from json_repair import repair_json

from src.core.logging import get_logger

logger = get_logger(__name__)


def robust_json_loads(text: str) -> Any:
    """先尝试标准 ``json.loads``，失败后使用 ``json_repair`` 修复再解析。

    Args:
        text: 待解析的 JSON 字符串

    Returns:
        解析后的 Python 对象

    Raises:
        json.JSONDecodeError: 标准解析和修复均失败时抛出
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.warning("标准JSON解析失败，尝试修复", raw_length=len(text) if text else 0)
        try:
            repaired = repair_json(text, return_objects=True)
            logger.info("JSON修复成功")
            return repaired
        except Exception as e:
            logger.error("JSON修复也失败", error=str(e))
            raise json.JSONDecodeError(f"repair also failed: {e}", text or "", 0) from e


def safe_json_loads(value: str | None, default: Any) -> Any:
    """安全解析 JSON 字段，失败时使用 ``json_repair`` 修复，仍失败则返回 default。"""
    if not value:
        return default
    try:
        return robust_json_loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _extract_json_str(text: str) -> str | None:
    """从 LLM 文本中提取 JSON 字符串。

    优先匹配 markdown code block（```json ... ```），
    否则回退到首个 ``{`` 到最后一个 ``}`` 之间的内容。
    无法定位时返回 None。
    """
    stripped = text.strip()

    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped)
    if code_block_match:
        return code_block_match.group(1).strip()

    json_start = stripped.find("{")
    json_end = stripped.rfind("}") + 1
    if json_start == -1 or json_end <= 0:
        return None
    return stripped[json_start:json_end]


def parse_llm_json_response(
    response: str,
    *,
    list_key: str = "test_cases",
    sort_key: str | None = None,
) -> list[dict[str, Any]]:
    """从 LLM 响应文本中解析 JSON 列表。

    支持 markdown code block 包裹和纯 JSON 文本。
    若解析结果为 dict，则取 list_key 对应的子列表；
    若为 list 则直接使用。可选按 sort_key 排序。

    解析失败时自动使用 ``json_repair`` 进行修复。
    """
    if not response:
        return []

    json_str = _extract_json_str(response)
    if json_str is None:
        logger.warning("LLM响应中未找到JSON内容")
        return []

    try:
        data = robust_json_loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"解析LLM JSON响应失败: {e}", error=str(e))
        return []

    if isinstance(data, dict):
        cases = data.get(list_key, [])
        if not isinstance(cases, list):
            return []
    elif isinstance(data, list):
        cases = data
    else:
        return []

    if sort_key:
        cases.sort(key=lambda c: c.get(sort_key, 0))

    return cases


def parse_llm_json_object(response: str) -> dict[str, Any]:
    """从 LLM 响应文本中解析出单个 JSON 对象。

    支持 markdown code block 包裹和纯 JSON 文本。与 ``parse_llm_json_response``
    返回列表不同，本函数返回单个 dict，适用于结构化对象（如安全审计结果）。
    解析失败或结果非 dict 时返回空 dict。

    Args:
        response: 待解析的 LLM 响应文本

    Returns:
        解析后的 dict；失败时返回空 dict
    """
    if not response:
        return {}

    json_str = _extract_json_str(response)
    if json_str is None:
        logger.warning("LLM响应中未找到JSON对象内容")
        return {}

    try:
        data = robust_json_loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"解析LLM JSON对象失败: {e}", error=str(e))
        return {}

    if isinstance(data, dict):
        return data
    return {}
