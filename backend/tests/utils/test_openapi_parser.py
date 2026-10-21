"""OpenAPIParser 单元测试。

覆盖：加载方式、版本检测、属性、查询、$ref 解析、
      魔术方法、格式化输出、server variables、边界场景。
"""

import json
from io import StringIO
from unittest.mock import patch

import pytest

from src.utils.parser.openapi_parser import OpenAPIParser

# ---------------------------------------------------------------------------
#  测试数据 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_v3_spec() -> dict:
    """最小化的 OpenAPI 3.0 文档。"""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Test API",
            "description": "A test API",
            "version": "1.0.0",
            "contact": {"name": "Tester", "email": "test@example.com", "url": "https://example.com"},
            "license": {"name": "MIT", "url": "https://mit.edu"},
        },
        "servers": [{"url": "https://api.example.com/v1", "description": "Production"}],
        "tags": [
            {"name": "users", "description": "User operations"},
            {"name": "admin", "description": "Admin operations"},
        ],
        "paths": {
            "/users": {
                "get": {
                    "summary": "List users",
                    "operationId": "listUsers",
                    "tags": ["users"],
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 10},
                            "description": "Max results",
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "array", "items": {"$ref": "#/components/schemas/User"}}
                                }
                            },
                        }
                    },
                },
                "post": {
                    "summary": "Create user",
                    "operationId": "createUser",
                    "tags": ["users"],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/User"}}},
                    },
                    "responses": {"201": {"description": "Created"}},
                },
            },
            "/users/{id}": {
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "User ID",
                    }
                ],
                "get": {
                    "summary": "Get user",
                    "operationId": "getUser",
                    "tags": ["users"],
                    "deprecated": True,
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/User"}}},
                        }
                    },
                },
                "delete": {
                    "summary": "Delete user",
                    "operationId": "deleteUser",
                    "tags": ["admin"],
                    "responses": {"204": {"description": "Deleted"}},
                },
            },
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "required": ["name", "email"],
                    "properties": {
                        "name": {"type": "string", "description": "User name"},
                        "email": {"type": "string", "format": "email", "description": "Email"},
                        "age": {"type": "integer", "description": "Age"},
                    },
                }
            },
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT auth",
                }
            },
        },
    }


@pytest.fixture()
def minimal_v2_spec() -> dict:
    """最小化的 Swagger 2.0 文档。"""
    return {
        "swagger": "2.0",
        "info": {"title": "Legacy API", "version": "0.9.0"},
        "host": "old.example.com",
        "basePath": "/api",
        "schemes": ["https"],
        "tags": [{"name": "items", "description": "Item ops"}],
        "paths": {
            "/items": {
                "get": {
                    "summary": "List items",
                    "operationId": "listItems",
                    "tags": ["items"],
                    "parameters": [{"name": "q", "in": "query", "type": "string", "description": "Search query"}],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "schema": {"type": "array", "items": {"$ref": "#/definitions/Item"}},
                        }
                    },
                }
            }
        },
        "definitions": {
            "Item": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                },
            }
        },
        "securityDefinitions": {"ApiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}},
    }


# ---------------------------------------------------------------------------
#  加载方式测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAPIParserLoading:
    """文档加载测试。"""

    def test_load_from_dict(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert parser.title == "Test API"

    def test_load_from_json_string(self, minimal_v3_spec):
        json_str = json.dumps(minimal_v3_spec)
        parser = OpenAPIParser(json_str)
        assert parser.title == "Test API"

    def test_load_from_json_file(self, minimal_v3_spec, tmp_path):
        filepath = tmp_path / "api.json"
        filepath.write_text(json.dumps(minimal_v3_spec), encoding="utf-8")

        parser = OpenAPIParser(str(filepath))
        assert parser.title == "Test API"

    def test_load_from_path_object(self, minimal_v3_spec, tmp_path):
        filepath = tmp_path / "spec.json"
        filepath.write_text(json.dumps(minimal_v3_spec), encoding="utf-8")

        parser = OpenAPIParser(filepath)
        assert parser.title == "Test API"

    def test_load_invalid_source_type_raises(self):
        with pytest.raises(ValueError, match="不支持的 source 类型"):
            OpenAPIParser(12345)

    def test_load_invalid_string_raises(self):
        with pytest.raises(ValueError, match="无法解析文档"):
            OpenAPIParser("definitely not json or yaml !!!{{{")

    def test_load_url_without_requests_raises(self, minimal_v3_spec):
        with (
            patch("src.utils.parser.openapi_parser._HAS_REQUESTS", False),
            pytest.raises(ImportError, match="requests"),
        ):
            OpenAPIParser("https://example.com/api.json")


# ---------------------------------------------------------------------------
#  版本检测测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAPIParserVersion:
    """版本检测测试。"""

    def test_v3_detection(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert parser.openapi_version == "3.0.0"
        assert parser.is_v3 is True
        assert parser.is_v2 is False

    def test_v2_detection(self, minimal_v2_spec):
        parser = OpenAPIParser(minimal_v2_spec)
        assert parser.openapi_version == "2.0"
        assert parser.is_v2 is True
        assert parser.is_v3 is False

    def test_missing_version_raises(self):
        with pytest.raises(ValueError, match="无法识别 OpenAPI 版本"):
            OpenAPIParser({"info": {"title": "No version"}})


# ---------------------------------------------------------------------------
#  属性测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAPIParserProperties:
    """属性访问测试。"""

    def test_info_properties(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert parser.title == "Test API"
        assert parser.description == "A test API"
        assert parser.version == "1.0.0"

    def test_base_url_v3(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert parser.base_url == "https://api.example.com/v1"

    def test_base_url_v2(self, minimal_v2_spec):
        parser = OpenAPIParser(minimal_v2_spec)
        assert parser.base_url == "https://old.example.com/api"

    def test_servers(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert len(parser.servers) == 1
        assert parser.servers[0]["url"] == "https://api.example.com/v1"

    def test_tags(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert len(parser.tags) == 2
        assert parser.tag_names == ["users", "admin"]

    def test_endpoints_count(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert len(parser.endpoints) == 4

    def test_endpoints_structure(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        ep = parser.get_endpoint("/users", "GET")
        assert ep is not None
        assert ep["method"] == "GET"
        assert ep["summary"] == "List users"
        assert ep["operation_id"] == "listUsers"
        assert "users" in ep["tags"]

    def test_schemas(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert len(parser.schemas) == 1
        user_schema = parser.schemas[0]
        assert user_schema["name"] == "User"
        assert "name" in user_schema["properties"]
        assert "email" in user_schema["required"]

    def test_security_schemes(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert len(parser.security_schemes) == 1
        assert parser.security_schemes[0]["name"] == "BearerAuth"
        assert parser.security_schemes[0]["scheme"] == "bearer"

    def test_paths(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert "/users" in parser.paths
        assert "/users/{id}" in parser.paths

    def test_stats(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        stats = parser.stats
        assert stats["total_endpoints"] == 4
        assert stats["total_schemas"] == 1
        assert stats["total_tags"] == 2
        assert stats["deprecated_count"] == 1
        assert "GET" in stats["methods"]

    def test_raw(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert parser.raw is minimal_v3_spec


# ---------------------------------------------------------------------------
#  查询方法测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAPIParserQuery:
    """查询方法测试。"""

    def test_get_endpoint_found(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        ep = parser.get_endpoint("/users/{id}", "GET")
        assert ep is not None
        assert ep["deprecated"] is True

    def test_get_endpoint_not_found(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert parser.get_endpoint("/nonexistent", "GET") is None

    def test_get_endpoint_case_insensitive_method(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        ep = parser.get_endpoint("/users", "get")
        assert ep is not None

    def test_get_endpoints_by_tag(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        admin_eps = parser.get_endpoints_by_tag("admin")
        assert len(admin_eps) == 1
        assert admin_eps[0]["operation_id"] == "deleteUser"

    def test_get_endpoints_by_method(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        get_eps = parser.get_endpoints_by_method("GET")
        assert len(get_eps) == 2

    def test_search_by_path(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        results = parser.search("users")
        assert len(results) >= 3

    def test_search_by_summary(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        results = parser.search("Delete")
        assert len(results) == 1

    def test_search_case_insensitive(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        results = parser.search("LIST")
        assert len(results) >= 1

    def test_get_schema_found(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        schema = parser.get_schema("User")
        assert schema is not None
        assert schema["type"] == "object"

    def test_get_schema_not_found(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert parser.get_schema("NonExistent") is None

    def test_get_endpoint_parameters(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        params = parser.get_endpoint_parameters("/users", "GET")
        assert len(params) == 1
        assert params[0]["name"] == "limit"

    def test_get_endpoint_parameters_not_found(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert parser.get_endpoint_parameters("/no", "GET") == []

    def test_get_endpoint_responses(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        resps = parser.get_endpoint_responses("/users", "GET")
        assert len(resps) == 1
        assert resps[0]["status_code"] == "200"


# ---------------------------------------------------------------------------
#  $ref 解析测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAPIParserRefResolution:
    """$ref 引用解析测试。"""

    def test_simple_ref_resolved(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        ep = parser.get_endpoint("/users/{id}", "GET")
        resp_content = ep["responses"][0]["content"]
        assert "application/json" in resp_content

    def test_nested_ref(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "T", "version": "1.0"},
            "paths": {
                "/test": {
                    "get": {
                        "summary": "test",
                        "responses": {
                            "200": {
                                "description": "ok",
                                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Wrapper"}}},
                            }
                        },
                    }
                }
            },
            "components": {
                "schemas": {
                    "Wrapper": {
                        "type": "object",
                        "properties": {"data": {"$ref": "#/components/schemas/Inner"}},
                    },
                    "Inner": {"type": "object", "properties": {"value": {"type": "string"}}},
                }
            },
        }
        parser = OpenAPIParser(spec)
        schema = parser.get_schema("Wrapper")
        assert "data" in schema["properties"]

    def test_invalid_ref_returns_empty(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "T", "version": "1.0"},
            "paths": {},
            "components": {"schemas": {}},
        }
        parser = OpenAPIParser(spec)
        result = parser._resolve_ref("#/nonexistent/path")
        assert result == {}

    def test_external_ref_returns_empty(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "T", "version": "1.0"},
            "paths": {},
        }
        parser = OpenAPIParser(spec)
        result = parser._resolve_ref("external.json#/definitions/Foo")
        assert result == {}


# ---------------------------------------------------------------------------
#  魔术方法测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAPIParserMagicMethods:
    """魔术方法测试。"""

    def test_len(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert len(parser) == 4

    def test_iter(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        endpoints = list(parser)
        assert len(endpoints) == 4

    def test_contains_path(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        assert "/users" in parser
        assert "/nonexistent" not in parser

    def test_getitem_by_index(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        ep = parser[0]
        assert "method" in ep
        assert "path" in ep

    def test_getitem_by_path(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        eps = parser["/users"]
        assert isinstance(eps, list)
        assert len(eps) == 2

    def test_getitem_by_path_and_method(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        ep = parser["/users:GET"]
        assert ep is not None
        assert ep["method"] == "GET"

    def test_getitem_invalid_key_raises(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        with pytest.raises(KeyError):
            _ = parser[3.14]

    def test_repr(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        r = repr(parser)
        assert "Test API" in r
        assert "1.0.0" in r


# ---------------------------------------------------------------------------
#  格式化输出测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAPIParserOutput:
    """格式化输出测试。"""

    def test_to_dict(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        d = parser.to_dict()
        assert "info" in d
        assert "endpoints" in d
        assert "schemas" in d
        assert "stats" in d
        assert "tags" in d

    def test_to_json(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        j = parser.to_json()
        parsed = json.loads(j)
        assert parsed["info"]["title"] == "Test API"

    def test_print_summary(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        output = StringIO()
        parser.print_summary(output=output)
        text = output.getvalue()
        assert "Test API" in text
        assert "1.0.0" in text

    def test_print_endpoints(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        output = StringIO()
        parser.print_endpoints(output=output)
        text = output.getvalue()
        assert "GET" in text
        assert "/users" in text

    def test_print_endpoints_by_tag(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        output = StringIO()
        parser.print_endpoints(tag="admin", output=output)
        text = output.getvalue()
        assert "DELETE" in text

    def test_print_endpoint_detail(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        output = StringIO()
        parser.print_endpoint_detail("/users", "GET", output=output)
        text = output.getvalue()
        assert "List users" in text
        assert "limit" in text

    def test_print_endpoint_detail_not_found(self, minimal_v3_spec):
        parser = OpenAPIParser(minimal_v3_spec)
        output = StringIO()
        parser.print_endpoint_detail("/nonexist", "GET", output=output)
        text = output.getvalue()
        assert "未找到接口" in text


# ---------------------------------------------------------------------------
#  Server Variables 测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAPIParserServerVariables:
    """Server variables 解析测试。"""

    def test_url_with_variables_resolved(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "T", "version": "1.0"},
            "servers": [
                {
                    "url": "https://{env}.example.com/{version}",
                    "variables": {
                        "env": {"default": "prod", "enum": ["prod", "staging"]},
                        "version": {"default": "v2"},
                    },
                }
            ],
            "paths": {},
        }
        parser = OpenAPIParser(spec)
        assert parser.base_url == "https://prod.example.com/v2"

    def test_empty_variables(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "T", "version": "1.0"},
            "servers": [{"url": "https://api.example.com"}],
            "paths": {},
        }
        parser = OpenAPIParser(spec)
        assert parser.base_url == "https://api.example.com"

    def test_parse_server_variables_none(self):
        result = OpenAPIParser._parse_server_variables(None)
        assert result == {}

    def test_parse_server_variables_empty_dict(self):
        result = OpenAPIParser._parse_server_variables({})
        assert result == {}

    def test_resolve_server_url_no_variables(self):
        result = OpenAPIParser._resolve_server_url("https://api.example.com", {})
        assert result == "https://api.example.com"


# ---------------------------------------------------------------------------
#  Swagger 2.0 特定测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAPIParserV2:
    """Swagger 2.0 文档特定测试。"""

    def test_v2_endpoints(self, minimal_v2_spec):
        parser = OpenAPIParser(minimal_v2_spec)
        assert len(parser.endpoints) == 1
        ep = parser.endpoints[0]
        assert ep["method"] == "GET"
        assert ep["path"] == "/items"

    def test_v2_schemas(self, minimal_v2_spec):
        parser = OpenAPIParser(minimal_v2_spec)
        assert len(parser.schemas) == 1
        assert parser.schemas[0]["name"] == "Item"

    def test_v2_security_schemes(self, minimal_v2_spec):
        parser = OpenAPIParser(minimal_v2_spec)
        assert len(parser.security_schemes) == 1
        assert parser.security_schemes[0]["name"] == "ApiKey"
        assert parser.security_schemes[0]["type"] == "apiKey"

    def test_v2_parameters(self, minimal_v2_spec):
        parser = OpenAPIParser(minimal_v2_spec)
        params = parser.get_endpoint_parameters("/items", "GET")
        assert len(params) == 1
        assert params[0]["name"] == "q"
        assert params[0]["in"] == "query"


# ---------------------------------------------------------------------------
#  边界场景测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAPIParserEdgeCases:
    """边界场景测试。"""

    def test_empty_paths(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Empty", "version": "1.0"},
            "paths": {},
        }
        parser = OpenAPIParser(spec)
        assert parser.endpoints == []
        assert parser.paths == []
        assert parser.stats["total_endpoints"] == 0

    def test_no_info(self):
        spec = {"openapi": "3.0.0", "paths": {}}
        parser = OpenAPIParser(spec)
        assert parser.title == ""
        assert parser.version == ""

    def test_no_tags(self):
        spec = {"openapi": "3.0.0", "info": {"title": "T", "version": "1.0"}, "paths": {}}
        parser = OpenAPIParser(spec)
        assert parser.tags == []
        assert parser.tag_names == []

    def test_no_schemas(self):
        spec = {"openapi": "3.0.0", "info": {"title": "T", "version": "1.0"}, "paths": {}}
        parser = OpenAPIParser(spec)
        assert parser.schemas == []

    def test_no_servers_v3(self):
        spec = {"openapi": "3.0.0", "info": {"title": "T", "version": "1.0"}, "paths": {}}
        parser = OpenAPIParser(spec)
        assert parser.base_url == ""
        assert parser.servers == []

    def test_type_str_allof(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "T", "version": "1.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Combo": {
                        "allOf": [
                            {"$ref": "#/components/schemas/Base"},
                            {"type": "object", "properties": {"extra": {"type": "string"}}},
                        ]
                    },
                    "Base": {"type": "object", "properties": {"id": {"type": "integer"}}},
                }
            },
        }
        parser = OpenAPIParser(spec)
        schemas = parser.schemas
        assert len(schemas) == 2
