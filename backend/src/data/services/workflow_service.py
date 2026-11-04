"""OpenAPI 文档上传与解析服务。

承接 ``api/v1/workflow.py`` 的业务编排：保存上传文件、解析并写入环境与接口。
"""

import json
import tempfile
import uuid
from pathlib import Path

from src.core.database.database_manager import init_database_from_config
from src.core.errors import ConflictError, ValidationError
from src.core.logging import get_logger
from src.data.schemas import EnvironmentCreate, EndpointCreate
from src.data.services import EnvironmentService, EndpointService
from src.utils.parser import OpenAPIParser

logger = get_logger(__name__)

# 上传文档的持久化目录，后续解析按该目录下的路径读取
_UPLOAD_DIR = Path("uploads")
_ALLOWED_SUFFIXES = (".json", ".yaml", ".yml")


class WorkflowService:
    """OpenAPI 文档上传与解析编排。"""

    @staticmethod
    def _build_environments(space_id: int, parser: OpenAPIParser) -> list[EnvironmentCreate]:
        """把 OpenAPI ``servers`` 转为环境创建参数。

        Args:
            space_id: 目标空间主键
            parser: 已加载的 OpenAPI 解析器

        Returns:
            环境创建参数列表，与 ``parser.base_url`` 相同的条目置为默认环境
        """
        return [
            EnvironmentCreate(
                space_id=space_id,
                name=server.get("description") or f"默认环境名称_{server.get('url', '')}",
                base_url=server.get("url", ""),
                description=server.get("description", ""),
                variables=str(server.get("variables", "")),
                is_default=1 if server.get("url", "") == parser.base_url else 2,
            )
            for server in parser.servers
        ]

    @staticmethod
    def _build_endpoints(space_id: int, parser: OpenAPIParser) -> list[EndpointCreate]:
        """把 OpenAPI 接口定义转为接口创建参数。

        结构字段预序列化为 JSON 字符串，``header`` 参数单独存一份，``content_type``
        取请求体的首个 media type，缺省为 ``application/json``。

        Args:
            space_id: 目标空间主键
            parser: 已加载的 OpenAPI 解析器

        Returns:
            接口创建参数列表，顺序与解析结果一致
        """
        result = []
        for ep in parser.endpoints:
            header_params = [p for p in ep.get("parameters", []) if p.get("in") == "header"]

            request_body = ep.get("request_body") or {}
            content_type = "application/json"
            if isinstance(request_body, dict) and request_body.get("content"):
                content_keys = list(request_body["content"].keys())
                if content_keys:
                    content_type = content_keys[0]

            result.append(
                EndpointCreate(
                    space_id=space_id,
                    operation_id=ep.get("operation_id", ""),
                    name=ep.get("summary", ""),
                    path=ep.get("path", ""),
                    method=ep.get("method", ""),
                    tags=json.dumps(ep.get("tags", []), ensure_ascii=False),
                    summary=ep.get("summary", ""),
                    description=ep.get("description", ""),
                    params=json.dumps(ep.get("parameters", []), ensure_ascii=False),
                    headers=json.dumps(header_params, ensure_ascii=False),
                    body=json.dumps(request_body, ensure_ascii=False),
                    responses=json.dumps(ep.get("responses", []), ensure_ascii=False),
                    security=json.dumps(ep.get("security", []), ensure_ascii=False),
                    content_type=content_type,
                    deprecated=1 if ep.get("deprecated", False) else 0,
                )
            )
        return result

    def save_upload(self, filename: str, content: bytes) -> str:
        """校验并保存上传的 OpenAPI 文档。

        副作用：在 ``uploads`` 目录写入新文件，文件名加随机前缀避免覆盖。

        Args:
            filename: 原始文件名，只取其 basename
            content: 文件内容

        Returns:
            保存后的绝对路径

        Raises:
            ValidationError: 文件名为空或后缀不在 ``.json`` / ``.yaml`` / ``.yml`` 内
        """
        if not filename:
            raise ValidationError("文件名不能为空")

        # 只取 basename，避免 ../ 形式的路径遍历
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            raise ValidationError("仅支持 JSON/YAML 格式文件")

        _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        saved_path = _UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe_name}"
        saved_path.write_bytes(content)

        resolved = saved_path.resolve()
        logger.info("OpenAPI 文档上传成功", filename=safe_name, path=str(resolved))
        return str(resolved)

    def parse_openapi(self, space_id: int, filename: str, content: bytes) -> dict:
        """解析 OpenAPI 文档并把环境与接口写入数据库。

        使用 ``init_database_from_config`` 独立开启会话，与请求级会话无关，事务在该
        会话上下文退出时提交；临时文件在 ``finally`` 中删除。

        副作用：写临时文件、写库并提交，环境与接口按 ``(space_id, name)`` /
        ``(space_id, path, method)`` 去重，已存在的条目被跳过。

        Args:
            space_id: 目标空间主键
            filename: 原始文件名，只用于判断后缀与日志
            content: 文件内容

        Returns:
            ``{"endpoint_count": int, "space_id": int}``，计数为解析出的条目数，
            非实际新增数

        Raises:
            ValidationError: 文件名为空、后缀不支持、解析失败或写入冲突
        """
        if not filename:
            raise ValidationError("文件名不能为空")

        suffix = Path(filename).suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            raise ValidationError("仅支持 JSON/YAML 格式文件")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="openapi_") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            logger.info(f"开始解析OpenAPI文档: {tmp_path}", path=str(tmp_path))
            parser = OpenAPIParser(tmp_path)
            logger.info(
                f"OpenAPI文档信息 - 标题: {parser.title}，base_url: {parser.base_url}",
                title=parser.title,
                base_url=parser.base_url,
            )

            with init_database_from_config().get_session() as session:
                env_service = EnvironmentService(session)
                endpoint_service = EndpointService(session)

                env_list = self._build_environments(space_id, parser)
                if env_list:
                    env_service.create_env(env_list)

                endpoint_list = self._build_endpoints(space_id, parser)
                if endpoint_list:
                    endpoint_service.create_endpoint(endpoint_list)

            logger.info(
                "OpenAPI 文档解析存储成功",
                filename=filename,
                space_id=space_id,
                endpoint_count=len(endpoint_list),
                environment_count=len(env_list)
            )

            return {"endpoint_count": len(endpoint_list), "space_id": space_id}
        except ConflictError as e:
            raise ValidationError(str(e)) from e
        except (FileNotFoundError, ValueError) as e:
            raise ValidationError(f"解析失败: {e}") from e
        finally:
            tmp_path.unlink(missing_ok=True)
