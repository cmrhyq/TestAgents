"""
OpenAPI 接口文档解析工具类

支持:
    - OpenAPI 2.0 (Swagger) / 3.0
    - JSON / YAML 格式
    - 本地文件 / URL / 字典 / JSON字符串
    - $ref 引用递归解析

使用示例:
    parser = OpenAPIParser("api.json")

    # 获取基本信息
    print(parser.title, parser.version, parser.base_url)

    # 获取所有接口
    for ep in parser.endpoints:
        print(ep["method"], ep["path"], ep["summary"])

    # 搜索接口
    results = parser.search("user")

    # 按标签筛选
    user_apis = parser.get_endpoints_by_tag("用户管理")

    # 获取某个接口详情
    detail = parser.get_endpoint("/users/{id}", "GET")

    # 获取所有数据模型
    schemas = parser.schemas

    # 统计
    print(parser.stats)
"""

import copy
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from src.core.logging import get_logger

logger = get_logger(__name__)

try:
    import yaml  # type: ignore[import-untyped]

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

try:
    import requests as _requests

    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# TODO [外部依赖] servers.variables 中的 enum 验证依赖运行时用户输入，当前仅使用 default 值替换
class OpenAPIParser:
    """
    OpenAPI / Swagger 接口文档解析工具类

    Args:
        source: 文档来源，支持以下类型:
            - dict: 已加载的文档字典
            - str:  文件路径 / URL(http开头) / JSON字符串
            - Path: 文件路径
    """

    _HTTP_METHODS = frozenset({"get", "post", "put", "delete", "patch", "head", "options", "trace"})

    def __init__(self, source: str | dict | Path):
        self._raw: dict = self._load(source)
        self._version: str = self._detect_version()
        self._ref_cache: dict = {}

        # 解析结果缓存(懒加载)
        self._info: dict | None = None
        self._tags: list | None = None
        self._endpoints: list | None = None
        self._schemas: list | None = None
        self._security_schemes: list | None = None

    # ----------------------------------------------------------------
    #  公开属性 - 基本信息
    # ----------------------------------------------------------------

    @property
    def raw(self) -> dict:
        """原始文档字典"""
        return self._raw

    @property
    def openapi_version(self) -> str:
        """OpenAPI 规范版本, 如 '2.0' / '3.0.0'"""
        return self._version

    @property
    def is_v2(self) -> bool:
        return self._version.startswith("2")

    @property
    def is_v3(self) -> bool:
        return self._version.startswith("3")

    @property
    def info(self) -> dict:
        """
        API 基本信息
        返回: {title, description, version, base_url, servers, contact, license}
        """
        if self._info is None:
            self._info = self._parse_info()
        return self._info

    @property
    def title(self) -> str:
        return self.info.get("title", "")

    @property
    def description(self) -> str:
        return self.info.get("description", "")

    @property
    def version(self) -> str:
        """API 业务版本号"""
        return self.info.get("version", "")

    @property
    def base_url(self) -> str:
        return self.info.get("base_url", "")

    @property
    def servers(self) -> list:
        return self.info.get("servers", [])

    # ----------------------------------------------------------------
    #  公开属性 - 核心数据
    # ----------------------------------------------------------------

    @property
    def tags(self) -> list:
        """
        标签列表
        返回: [{"name": "xxx", "description": "xxx"}, ...]
        """
        if self._tags is None:
            self._tags = [
                {"name": t.get("name", ""), "description": t.get("description", "")} for t in self._raw.get("tags", [])
            ]
        return self._tags

    @property
    def tag_names(self) -> list:
        """所有标签名"""
        return [t["name"] for t in self.tags]

    @property
    def endpoints(self) -> list:
        """
        所有接口列表，每个接口是一个字典:
        {
            "method": "GET",
            "path": "/users/{id}",
            "summary": "获取用户",
            "description": "...",
            "operation_id": "getUser",
            "tags": ["用户管理"],
            "deprecated": False,
            "parameters": [...],
            "request_body": {...} or None,
            "responses": [...],
            "security": [...]
        }
        """
        if self._endpoints is None:
            self._endpoints = self._parse_endpoints()
        return self._endpoints

    @property
    def schemas(self) -> list:
        """
        所有数据模型
        返回: [{"name": "User", "type": "object", "description": "...",
                "required": [...], "properties": {...}}, ...]
        """
        if self._schemas is None:
            self._schemas = self._parse_schemas()
        return self._schemas

    @property
    def security_schemes(self) -> list:
        """安全方案列表"""
        if self._security_schemes is None:
            self._security_schemes = self._parse_security_schemes()
        return self._security_schemes

    @property
    def paths(self) -> list:
        """所有接口路径(去重)"""
        return sorted(set(ep["path"] for ep in self.endpoints))

    @property
    def stats(self) -> dict:
        """
        统计信息
        返回: {total_endpoints, total_schemas, total_tags, methods, deprecated_count}
        """
        methods: dict = {}
        deprecated = 0
        for ep in self.endpoints:
            m = ep["method"]
            methods[m] = methods.get(m, 0) + 1
            if ep["deprecated"]:
                deprecated += 1

        return {
            "total_endpoints": len(self.endpoints),
            "total_schemas": len(self.schemas),
            "total_tags": len(self.tags),
            "methods": methods,
            "deprecated_count": deprecated,
        }

    # ----------------------------------------------------------------
    #  公开方法 - 查询 & 过滤
    # ----------------------------------------------------------------

    def get_endpoint(self, path: str, method: str) -> dict | None:
        """
        获取指定接口

        Args:
            path: 接口路径, 如 "/users/{id}"
            method: HTTP 方法, 如 "GET"

        Returns:
            接口字典 或 None
        """
        method = method.upper()
        for ep in self.endpoints:
            if ep["path"] == path and ep["method"] == method:
                return ep
        return None

    def get_endpoints_by_tag(self, tag: str) -> list:
        """按标签筛选接口"""
        return [ep for ep in self.endpoints if tag in ep["tags"]]

    def get_endpoints_by_method(self, method: str) -> list:
        """按 HTTP 方法筛选接口"""
        method = method.upper()
        return [ep for ep in self.endpoints if ep["method"] == method]

    def search(self, keyword: str) -> list:
        """
        搜索接口 (匹配 path / summary / description / operation_id)

        Args:
            keyword: 搜索关键词（不区分大小写）

        Returns:
            匹配的接口列表
        """
        kw = keyword.lower()
        results = []
        for ep in self.endpoints:
            if (
                kw in ep["path"].lower()
                or kw in ep["summary"].lower()
                or kw in ep["description"].lower()
                or kw in ep["operation_id"].lower()
            ):
                results.append(ep)
        return results

    def get_schema(self, name: str) -> dict | None:
        """按名称获取数据模型"""
        for s in self.schemas:
            if s["name"] == name:
                return s
        return None

    def get_endpoint_parameters(self, path: str, method: str) -> list:
        """获取指定接口的参数列表"""
        ep = self.get_endpoint(path, method)
        return ep["parameters"] if ep else []

    def get_endpoint_responses(self, path: str, method: str) -> list:
        """获取指定接口的响应列表"""
        ep = self.get_endpoint(path, method)
        return ep["responses"] if ep else []

    # ----------------------------------------------------------------
    #  公开方法 - 格式化输出
    # ----------------------------------------------------------------

    def print_summary(self, output: TextIO | None = None):
        """打印文档摘要到终端

        Args:
            output: 输出流，默认为 sys.stdout
        """
        out = output or sys.stdout
        out.write(f"\n{'=' * 60}\n")
        out.write(f"  {self.title}  (v{self.version})\n")
        out.write(f"  {self.description}\n")
        if self.base_url:
            out.write(f"  Base URL: {self.base_url}\n")
        out.write(f"{'=' * 60}\n")
        s = self.stats
        out.write(
            f"  接口: {s['total_endpoints']}  "
            f"模型: {s['total_schemas']}  "
            f"标签: {s['total_tags']}  "
            f"已废弃: {s['deprecated_count']}\n"
        )
        out.write(f"  方法: {s['methods']}\n\n")

    def print_endpoints(self, tag: str | None = None, output: TextIO | None = None):
        """
        打印接口列表

        Args:
            tag: 可选, 只打印指定标签下的接口
            output: 输出流，默认为 sys.stdout
        """
        out = output or sys.stdout
        eps = self.get_endpoints_by_tag(tag) if tag else self.endpoints
        for ep in eps:
            dep = " [废弃]" if ep["deprecated"] else ""
            out.write(f"  {ep['method']:7s} {ep['path']:40s} {ep['summary']}{dep}\n")

    def print_endpoint_detail(self, path: str, method: str, output: TextIO | None = None):
        """打印单个接口详情

        Args:
            path: 接口路径
            method: HTTP 方法
            output: 输出流，默认为 sys.stdout
        """
        out = output or sys.stdout
        ep = self.get_endpoint(path, method)
        if not ep:
            out.write(f"  未找到接口: {method} {path}\n")
            return

        out.write(f"\n  {ep['method']} {ep['path']}\n")
        out.write(f"  {'─' * 56}\n")
        if ep["summary"]:
            out.write(f"  摘要: {ep['summary']}\n")
        if ep["description"]:
            out.write(f"  描述: {ep['description']}\n")
        if ep["tags"]:
            out.write(f"  标签: {', '.join(ep['tags'])}\n")
        if ep["deprecated"]:
            out.write("  状态: 已废弃\n")

        if ep["parameters"]:
            out.write("\n  参数:\n")
            out.write(f"  {'名称':<20s} {'位置':<8s} {'类型':<15s} {'必填':<5s} 描述\n")
            out.write(f"  {'─' * 20} {'─' * 8} {'─' * 15} {'─' * 5} {'─' * 20}\n")
            for p in ep["parameters"]:
                req = "是" if p["required"] else ""
                out.write(f"  {p['name']:<20s} {p['in']:<8s} {p['type']:<15s} {req:<5s} {p['description']}\n")

        if ep["request_body"]:
            rb = ep["request_body"]
            out.write(f"\n  请求体: {'(必填)' if rb['required'] else ''}\n")
            for ct, schema in rb["content"].items():
                out.write(f"    Content-Type: {ct}\n")
                self._print_schema_props(schema.get("schema", {}), indent=6, output=out)

        if ep["responses"]:
            out.write("\n  响应:\n")
            for r in ep["responses"]:
                out.write(f"    {r['status_code']}: {r['description']}\n")
                for ct, schema in r.get("content", {}).items():
                    out.write(f"      Content-Type: {ct}\n")
                    self._print_schema_props(schema.get("schema", {}), indent=8, output=out)
        out.write("\n")

    def to_dict(self) -> dict:
        """导出为结构化字典"""
        return {
            "info": self.info,
            "stats": self.stats,
            "tags": self.tags,
            "endpoints": self.endpoints,
            "schemas": self.schemas,
        }

    def to_json(self, indent: int = 2) -> str:
        """导出为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    # ================================================================
    #  内部方法 - 加载文档
    # ================================================================

    @staticmethod
    def _load(source: str | dict | Path) -> dict:
        """加载文档"""
        if isinstance(source, dict):
            return source

        if isinstance(source, Path):
            return OpenAPIParser._load_file(source)

        if isinstance(source, str):
            if source.startswith(("http://", "https://")):
                return OpenAPIParser._load_url(source)

            path = Path(source)
            if path.exists():
                return OpenAPIParser._load_file(path)

            # 当作 JSON/YAML 字符串
            return OpenAPIParser._load_string(source)

        raise ValueError(f"不支持的 source 类型: {type(source)}")

    @staticmethod
    def _load_file(filepath: Path) -> dict:
        content = filepath.read_text(encoding="utf-8")
        if filepath.suffix.lower() in (".yaml", ".yml"):
            if not _HAS_YAML:
                raise ImportError("解析 YAML 需要安装 pyyaml: pip install pyyaml")
            return yaml.safe_load(content)
        if filepath.suffix.lower() == ".json":
            return json.loads(content)
        return OpenAPIParser._load_string(content)

    @staticmethod
    def _load_url(url: str) -> dict:
        if not _HAS_REQUESTS:
            raise ImportError("远程加载需要安装 requests: pip install requests")
        resp = _requests.get(url, timeout=30)
        resp.raise_for_status()
        return OpenAPIParser._load_string(resp.text)

    @staticmethod
    def _load_string(text: str) -> dict:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
        if _HAS_YAML:
            try:
                result = yaml.safe_load(text)
                if isinstance(result, dict):
                    return result
            except Exception:
                pass
        raise ValueError("无法解析文档, 请确认是合法的 JSON 或 YAML")

    # ================================================================
    #  内部方法 - 版本检测 & $ref 解析
    # ================================================================

    def _detect_version(self) -> str:
        if "swagger" in self._raw:
            return str(self._raw["swagger"])
        if "openapi" in self._raw:
            return str(self._raw["openapi"])
        raise ValueError("无法识别 OpenAPI 版本, 文档缺少 'swagger' 或 'openapi' 字段")

    def _resolve_ref(self, ref: str) -> dict:
        """解析 $ref 引用, 如 '#/definitions/User'"""
        if ref in self._ref_cache:
            return self._ref_cache[ref]

        if not ref.startswith("#/"):
            return {}

        node = self._raw
        for part in ref[2:].split("/"):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return {}

        resolved = self._deep_resolve(node) if isinstance(node, dict) else node
        self._ref_cache[ref] = resolved
        return resolved

    def _deep_resolve(self, obj: Any, depth: int = 0) -> Any:
        """递归解析所有 $ref"""
        if depth > 30:
            return obj
        if isinstance(obj, dict):
            if "$ref" in obj:
                return self._deep_resolve(copy.deepcopy(self._resolve_ref(obj["$ref"])), depth + 1)
            return {k: self._deep_resolve(v, depth + 1) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._deep_resolve(item, depth + 1) for item in obj]
        return obj

    def _type_str(self, schema: dict) -> str:
        """将 schema 转为可读的类型字符串"""
        if "$ref" in schema:
            return schema["$ref"].rsplit("/", 1)[-1]

        t = schema.get("type", "")
        if t == "array":
            items = schema.get("items", {})
            return f"array[{self._type_str(items)}]"
        if "allOf" in schema:
            return " & ".join(self._type_str(i) for i in schema["allOf"])
        if "oneOf" in schema:
            return " | ".join(self._type_str(i) for i in schema["oneOf"])
        if "anyOf" in schema:
            return " | ".join(self._type_str(i) for i in schema["anyOf"])

        fmt = schema.get("format", "")
        return f"{t}({fmt})" if fmt else (t or "object")

    # ================================================================
    #  内部方法 - 解析各部分
    # ================================================================

    def _parse_info(self) -> dict:
        raw_info = self._raw.get("info", {})
        contact = raw_info.get("contact", {})
        lic = raw_info.get("license", {})

        result = {
            "title": raw_info.get("title", ""),
            "description": raw_info.get("description", ""),
            "version": raw_info.get("version", ""),
            "contact": {
                "name": contact.get("name", ""),
                "email": contact.get("email", ""),
                "url": contact.get("url", ""),
            }
            if contact
            else None,
            "license": {
                "name": lic.get("name", ""),
                "url": lic.get("url", ""),
            }
            if lic
            else None,
            "base_url": "",
            "servers": [],
        }

        if self.is_v2:
            host = self._raw.get("host", "")
            base_path = self._raw.get("basePath", "")
            schemes = self._raw.get("schemes", ["https"])
            if host:
                result["base_url"] = f"{schemes[0]}://{host}{base_path}"
                result["servers"] = [{"url": result["base_url"], "description": "", "variables": {}}]
        else:
            for s in self._raw.get("servers", []):
                variables = self._parse_server_variables(s.get("variables", "{}"))
                resolved_url = self._resolve_server_url(s.get("url", ""), variables)
                result["servers"].append(
                    {
                        "url": resolved_url,
                        "description": s.get("description", ""),
                        "variables": variables,
                    }
                )
            if result["servers"]:
                result["base_url"] = result["servers"][0]["url"]

        return result

    @staticmethod
    def _parse_server_variables(raw_variables: dict) -> dict:
        """解析 servers.variables 定义。

        Args:
            raw_variables: OpenAPI 3.x servers[].variables 原始字典

        Returns:
            解析后的变量字典，格式:
            {
                "var_name": {
                    "default": "default_value",
                    "enum": ["val1", "val2"],
                    "description": "..."
                }
            }
        """
        if not raw_variables or not isinstance(raw_variables, dict):
            return {}

        variables = {}
        for name, var_data in raw_variables.items():
            if not isinstance(var_data, dict):
                continue
            variables[name] = {
                "default": var_data.get("default", ""),
                "enum": var_data.get("enum", []),
                "description": var_data.get("description", ""),
            }
        return variables

    @staticmethod
    def _resolve_server_url(url: str, variables: dict) -> str:
        """用 variables 的 default 值替换 server URL 中的 {variable} 占位符。

        Args:
            url: 含 {variable} 占位符的 server URL
            variables: 已解析的 variables 字典

        Returns:
            替换占位符后的完整 URL
        """
        if not variables:
            return url

        resolved = url
        for name, var_info in variables.items():
            placeholder = "{" + name + "}"
            if placeholder in resolved:
                resolved = resolved.replace(placeholder, var_info.get("default", ""))
        return resolved

    def _parse_security_schemes(self) -> list:
        if self.is_v2:
            defs = self._raw.get("securityDefinitions", {})
        else:
            defs = self._raw.get("components", {}).get("securitySchemes", {})

        result = []
        for name, data in defs.items():
            result.append(
                {
                    "name": name,
                    "type": data.get("type", ""),
                    "description": data.get("description", ""),
                    "in": data.get("in", ""),
                    "scheme": data.get("scheme", ""),
                    "bearer_format": data.get("bearerFormat", ""),
                }
            )
        return result

    def _parse_schemas(self) -> list:
        if self.is_v2:
            defs = self._raw.get("definitions", {})
        else:
            defs = self._raw.get("components", {}).get("schemas", {})

        result = []
        for name, raw_schema in defs.items():
            resolved = self._deep_resolve(raw_schema)
            required_fields = resolved.get("required", [])

            properties = {}
            for pname, pdata in resolved.get("properties", {}).items():
                pdata = self._deep_resolve(pdata)
                properties[pname] = {
                    "type": self._type_str(pdata),
                    "description": pdata.get("description", ""),
                    "format": pdata.get("format", ""),
                    "enum": pdata.get("enum", []),
                    "default": pdata.get("default"),
                    "example": pdata.get("example"),
                }

            result.append(
                {
                    "name": name,
                    "type": resolved.get("type", "object"),
                    "description": resolved.get("description", ""),
                    "required": required_fields,
                    "properties": properties,
                }
            )

        return result

    def _parse_endpoints(self) -> list:
        endpoints = []
        for path, path_item in self._raw.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue

            path_params = path_item.get("parameters", [])

            for method in self._HTTP_METHODS:
                if method not in path_item:
                    continue
                op = path_item[method]
                if not isinstance(op, dict):
                    continue
                endpoints.append(self._parse_operation(path, method, op, path_params))

        endpoints.sort(key=lambda e: (e["path"], e["method"]))
        return endpoints

    def _parse_operation(self, path: str, method: str, op: dict, path_params: list) -> dict:
        endpoint = {
            "method": method.upper(),
            "path": path,
            "summary": op.get("summary", ""),
            "description": op.get("description", ""),
            "operation_id": op.get("operationId", ""),
            "tags": op.get("tags", []),
            "deprecated": op.get("deprecated", False),
            "security": op.get("security", []),
            "parameters": [],
            "request_body": None,
            "responses": [],
        }

        # ---------- 参数 ----------
        all_params = path_params + op.get("parameters", [])
        for raw_p in all_params:
            raw_p = self._deep_resolve(raw_p)
            endpoint["parameters"].append(self._parse_parameter(raw_p))

        # ---------- 请求体 (v3) ----------
        if self.is_v3 and "requestBody" in op:
            endpoint["request_body"] = self._parse_request_body(op["requestBody"])

        # ---------- 响应 ----------
        for code, raw_resp in op.get("responses", {}).items():
            raw_resp = self._deep_resolve(raw_resp)
            endpoint["responses"].append(self._parse_response(str(code), raw_resp))

        return endpoint

    def _parse_parameter(self, raw: dict) -> dict:
        # v2 body 参数
        if raw.get("in") == "body":
            schema = self._deep_resolve(raw.get("schema", {}))
            return {
                "name": raw.get("name", "body"),
                "in": "body",
                "type": self._type_str(schema),
                "required": raw.get("required", False),
                "description": raw.get("description", ""),
                "default": None,
                "enum": [],
                "schema": schema,
            }

        schema = raw.get("schema", {})
        if schema:
            schema = self._deep_resolve(schema)
            ptype = self._type_str(schema)
        else:
            ptype = raw.get("type", "string")
            fmt = raw.get("format", "")
            if fmt:
                ptype = f"{ptype}({fmt})"

        return {
            "name": raw.get("name", ""),
            "in": raw.get("in", ""),
            "type": ptype,
            "required": raw.get("required", False),
            "description": raw.get("description", ""),
            "default": raw.get("default", schema.get("default") if isinstance(schema, dict) else None),
            "enum": raw.get("enum", schema.get("enum", []) if isinstance(schema, dict) else []),
            "schema": schema if isinstance(schema, dict) else {},
        }

    def _parse_request_body(self, raw: dict) -> dict:
        raw = self._deep_resolve(raw)
        rb = {
            "description": raw.get("description", ""),
            "required": raw.get("required", False),
            "content": {},
        }
        for media_type, media_data in raw.get("content", {}).items():
            schema = self._deep_resolve(media_data.get("schema", {}))
            rb["content"][media_type] = {
                "schema": schema,
                "type": self._type_str(schema),
            }
        return rb

    def _parse_response(self, code: str, raw: dict) -> dict:
        resp = {
            "status_code": code,
            "description": raw.get("description", ""),
            "content": {},
        }

        if self.is_v2:
            schema = raw.get("schema")
            if schema:
                schema = self._deep_resolve(schema)
                resp["content"]["default"] = {
                    "schema": schema,
                    "type": self._type_str(schema),
                }
        else:
            for media_type, media_data in raw.get("content", {}).items():
                schema = self._deep_resolve(media_data.get("schema", {}))
                resp["content"][media_type] = {
                    "schema": schema,
                    "type": self._type_str(schema),
                }

        return resp

    def _print_schema_props(self, schema: dict, indent: int = 4, output: TextIO | None = None):
        """辅助: 打印 schema 属性"""
        out = output or sys.stdout
        props = schema.get("properties", {})
        required = schema.get("required", [])
        prefix = " " * indent
        for name, prop in props.items():
            req = "*" if name in required else " "
            ptype = prop.get("type", self._type_str(prop))
            desc = prop.get("description", "")
            out.write(f"{prefix}{req} {name}: {ptype}  {desc}\n")

    # ================================================================
    #  魔术方法
    # ================================================================

    def __repr__(self):
        return f"OpenAPIParser(title='{self.title}', version='{self.version}', endpoints={len(self.endpoints)})"

    def __len__(self):
        """返回接口数量"""
        return len(self.endpoints)

    def __iter__(self):
        """迭代所有接口"""
        return iter(self.endpoints)

    def __contains__(self, path: str):
        """判断路径是否存在"""
        return path in self.paths

    def __getitem__(self, key):
        """
        支持:
            parser[0]             -> 按索引取接口
            parser["/users"]      -> 取路径下所有接口
            parser["/users:GET"]  -> 取特定接口
        """
        if isinstance(key, int):
            return self.endpoints[key]
        if isinstance(key, str):
            if ":" in key:
                path, method = key.rsplit(":", 1)
                return self.get_endpoint(path, method)
            return [ep for ep in self.endpoints if ep["path"] == key]
        raise KeyError(key)
