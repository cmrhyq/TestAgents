"""简易 JSONPath 提取工具。

支持 ``$.a.b.c`` 与 ``$.a[0].b`` 两种路径格式，供断言引擎与缓存解析器共用。
"""

import re
from typing import Any

_BRACKET_SEGMENT = re.compile(r"^(\w+)\[(\d+)\]$")


def tokenize_path(path: str) -> list[str]:
    """将 ``a.b[0].c`` 拆分为 ``["a", "b", "0", "c"]``。"""
    tokens: list[str] = []
    for segment in path.split("."):
        if not segment:
            continue
        bracket_match = _BRACKET_SEGMENT.match(segment)
        if bracket_match:
            tokens.append(bracket_match.group(1))
            tokens.append(bracket_match.group(2))
        else:
            tokens.append(segment)
    return tokens


def extract_jsonpath(data: Any, path: str) -> Any:
    """按简易 JSONPath 从 ``data`` 中提取值，未命中返回 None。"""
    if data is None:
        return None

    if path == "$":
        return data

    stripped = path.lstrip("$").lstrip(".")
    if not stripped:
        return data

    current = data
    for token in tokenize_path(stripped):
        if current is None:
            return None
        if token.isdigit():
            idx = int(token)
            if isinstance(current, list) and idx < len(current):
                current = current[idx]
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(token)
        else:
            return None

    return current
