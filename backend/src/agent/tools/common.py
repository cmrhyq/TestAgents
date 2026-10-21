"""工具模块私有共享辅助函数（不对外导出，避免污染工具列表）。"""

from typing import Any

from src.utils.json_utils import safe_json_loads


def as_object(value: Any) -> Any:
    """将 JSON 字符串解析为 Python 对象；非字符串或解析失败时原样返回。"""
    if not isinstance(value, str):
        return value
    parsed = safe_json_loads(value, None)
    return parsed if parsed is not None else value
