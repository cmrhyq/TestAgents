"""文档域 LangChain Tools：OpenAPI/Swagger 文档解析、搜索、详情。

包装 OpenAPIParser 为 3 个原子 Tool，带进程内解析缓存以保持离线快速特性。
"""

import json

from langchain_core.tools import tool

from src.core.logging import get_logger
from src.utils.parser.openapi_parser import OpenAPIParser

logger = get_logger(__name__)

# OpenAPI 解析器缓存：避免同一文档被反复解析（离线快速特性），上限 20 份
_PARSER_CACHE: dict[str, OpenAPIParser] = {}
_PARSER_CACHE_MAX = 20


def _get_parser(source: str) -> OpenAPIParser:
    """获取（并缓存）OpenAPI 解析器实例。"""
    parser = _PARSER_CACHE.get(source)
    if parser is None:
        parser = OpenAPIParser(source)
        if len(_PARSER_CACHE) >= _PARSER_CACHE_MAX:
            _PARSER_CACHE.pop(next(iter(_PARSER_CACHE)))
        _PARSER_CACHE[source] = parser
    return parser


@tool
def parse_openapi(source: str) -> str:
    """解析 OpenAPI/Swagger 接口文档，返回文档信息、统计与接口清单。

    Args:
        source: 文档来源 —— 文件路径 / URL(以http开头) / JSON 字符串

    Returns:
        JSON 字符串: {info: {...}, stats: {...}, endpoints: [{method, path, summary, tags, deprecated}]}
    """
    try:
        parser = _get_parser(source)
        return json.dumps(
            {
                "info": parser.info,
                "stats": parser.stats,
                "endpoints": [
                    {
                        "method": ep["method"],
                        "path": ep["path"],
                        "summary": ep["summary"],
                        "tags": ep["tags"],
                        "deprecated": ep["deprecated"],
                    }
                    for ep in parser.endpoints
                ],
            },
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"OpenAPI 解析失败: {e}", error=str(e))
        return json.dumps({"error": f"解析 OpenAPI 文档失败: {e}"}, ensure_ascii=False)


@tool
def search_endpoint(source: str, keyword: str) -> str:
    """在 OpenAPI 文档中按关键词搜索接口（匹配 path/summary/description/operation_id，不区分大小写）。

    Args:
        source: 文档来源 —— 文件路径 / URL(以http开头) / JSON 字符串
        keyword: 搜索关键词，如 "user"、"login"

    Returns:
        匹配的接口完整列表（JSON 字符串）
    """
    try:
        parser = _get_parser(source)
        results = parser.search(keyword)
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        logger.error(f"接口搜索失败: {e}", keyword=keyword, error=str(e))
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def get_endpoint_detail(source: str, path: str, method: str) -> str:
    """获取 OpenAPI 文档中单个接口的完整详情（参数、请求体、响应结构）。

    Args:
        source: 文档来源 —— 文件路径 / URL(以http开头) / JSON 字符串
        path: 接口路径，如 "/users/{id}"
        method: HTTP 方法，如 "get"

    Returns:
        接口详情 JSON 字符串；未找到返回 {}
    """
    try:
        parser = _get_parser(source)
        endpoint = parser.get_endpoint(path, method)
        return json.dumps(endpoint or {}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"接口详情获取失败: {e}", path=path, method=method, error=str(e))
        return json.dumps({"error": str(e)}, ensure_ascii=False)
