"""工作流触发服务。

承接 ``api/v1/workflow.py`` 的业务：OpenAPI 文档上传保存与解析编排。
路由层只负责收文件、调 Service、返回 schema。
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

# 上传的 OpenAPI 文档持久化目录，供后续解析时读取
_UPLOAD_DIR = Path("uploads")
_ALLOWED_SUFFIXES = (".json", ".yaml", ".yml")


class WorkflowService:
    """OpenAPI 文档上传与解析编排。"""

    @staticmethod
    def _build_environments(space_id: int, parser: OpenAPIParser) -> list[EnvironmentCreate]:
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
        """校验并保存上传的 OpenAPI 文档，返回绝对路径。

        Args:
            filename: 原始文件名
            content: 文件内容

        Returns:
            服务器保存后的绝对路径

        Raises:
            ValidationError: 文件名或后缀非法
        """
        if not filename:
            raise ValidationError("文件名不能为空")

        # 仅保留文件名部分，防止路径遍历（如 ../../etc/passwd）
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
        """上传并解析 OpenAPI 文档，解析接口并存入数据库。

        Args:
            space_id: 空间id
            filename: 原始文件名
            content: 文件内容

        Returns:
            {"endpoint_count": int, "space_id": int}

        Raises:
            ValidationError: 文件名非法或解析失败
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
