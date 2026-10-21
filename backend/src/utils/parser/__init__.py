"""
输入解析器包

提供用户原始输入（自定义 JSON）与标准 OpenAPI 文档的解析能力。
"""

from src.utils.parser.openapi_parser import OpenAPIParser

__all__ = [
    "OpenAPIParser",
]
