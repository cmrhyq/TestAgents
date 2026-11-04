"""JSON 解析公共工具。

统一带 ``json_repair`` 兜底的解析入口，以及从 LLM 响应文本中提取 JSON 的辅助函数。
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
    """解析 JSON 字段，失败时返回默认值。

    Args:
        value: 待解析字符串；空值时直接返回 default
        default: 解析失败时的返回值

    Returns:
        解析结果或 default
    """
    if not value:
        return default
    try:
        return robust_json_loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _extract_json_str(text: str) -> str | None:
    """从 LLM 文本中定位 JSON 片段。

    优先取 markdown 代码块内容，其次取首个 ``{`` 到末个 ``}`` 之间的文本。

    Args:
        text: LLM 原始响应

    Returns:
        提取出的 JSON 字符串；无法定位时返回 None
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
    list_key: str = "items",
    sort_key: str | None = None,
) -> list[dict[str, Any]]:
    """从 LLM 响应文本中解析 JSON 列表。

    结果为 dict 时取 ``list_key`` 对应的子列表，为 list 时直接使用；
    解析失败或类型不符时返回空列表。

    Args:
        response: LLM 原始响应
        list_key: 结果为 dict 时提取子列表所用的键
        sort_key: 非空时按该字段升序排序，缺失字段按 0 处理

    Returns:
        元素为 dict 的列表；失败时返回空列表
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
    """从 LLM 响应文本中解析单个 JSON 对象。

    与 ``parse_llm_json_response`` 的区别是不做列表包装，适用于结构化对象结果。

    Args:
        response: LLM 原始响应

    Returns:
        解析后的 dict；解析失败或结果非 dict 时返回空 dict
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


def as_object(value: Any) -> Any:
    """将 JSON 字符串解析为 Python 对象；非字符串或解析失败时原样返回。"""
    if not isinstance(value, str):
        return value
    parsed = safe_json_loads(value, None)
    return parsed if parsed is not None else value
