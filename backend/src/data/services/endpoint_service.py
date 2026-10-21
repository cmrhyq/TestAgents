import json

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.core.errors import ConflictError, ValidationError
from src.core.logging import get_logger
from src.data.models import Endpoint
from src.data.repositories import EndpointRepository
from src.data.schemas.endpoint import EndpointCreate
from src.data.services.base_service import BaseService

logger = get_logger(__name__)


class EndpointService(BaseService[Endpoint, EndpointRepository]):
    def __init__(self, session: Session):
        super().__init__(session, EndpointRepository(session))

    def create_one(self, data: EndpointCreate) -> Endpoint:
        if data.space_id is None:
            raise ValidationError("接口必须关联空间")
        if self.repo.check_duplicate(data.space_id, data.path, data.method):
            raise ConflictError(f"接口已存在: {data.method} {data.path}")
        values = data.model_dump()
        for field in ("tags", "params", "headers", "body", "responses", "security"):
            if isinstance(values.get(field), (list, dict)):
                values[field] = json.dumps(values[field], ensure_ascii=False)
        values["method"] = values["method"].upper()
        return self.create(Endpoint(**values))

    def list_endpoints(
        self, space_id: int | None, method: str | None, keyword: str | None, page: int, page_size: int
    ):
        filters = []
        if space_id is not None:
            filters.append(Endpoint.space_id == space_id)
        if method:
            filters.append(Endpoint.method == method.upper())
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    Endpoint.name.ilike(pattern),
                    Endpoint.path.ilike(pattern),
                    Endpoint.summary.ilike(pattern),
                    Endpoint.method.ilike(pattern),
                )
            )
        return self.list(page, page_size, *filters)

    def update_endpoint(self, endpoint_id: int, fields: dict) -> Endpoint:
        if "path" in fields or "method" in fields:
            current = self.get_or_raise(endpoint_id, "接口不存在")
            new_path = fields.get("path", current.path)
            new_method = str(fields.get("method", current.method)).upper()
            duplicates = self.repo.find_by_identity(current.space_id, new_path, new_method)
            if any(dup.id != endpoint_id for dup in duplicates):
                raise ConflictError(f"接口已存在: {new_method} {new_path}")
        for field in ("tags", "params", "headers", "body", "responses", "security"):
            if isinstance(fields.get(field), (list, dict)):
                fields[field] = json.dumps(fields[field], ensure_ascii=False)
        if fields.get("method"):
            fields["method"] = str(fields["method"]).upper()
        return self.update(endpoint_id, **fields)

    def get_active_by_ids(self, endpoint_ids: list[int]) -> list[Endpoint]:
        return self.repo.get_active_by_ids(endpoint_ids)

    def list_active(self, space_id: int) -> list[Endpoint]:
        return self.repo.get_by_space(space_id, active_only=True)

    def _get_existing_keys(self, endpoint_list: list[EndpointCreate]) -> set:
        """批量查询已存在的 (space_id, path, method) 组合"""
        space_ids = {endpoint.space_id for endpoint in endpoint_list}
        paths = {endpoint.path for endpoint in endpoint_list}
        methods = {endpoint.method for endpoint in endpoint_list}
        existing = self.repo.bulk_query(space_ids, paths, methods)
        return {(item.space_id, item.path, item.method) for item in existing}

    def create_endpoint(self, endpoints: list[EndpointCreate]) -> list[Endpoint]:
        if len(endpoints) == 0:
            logger.warning("无接口数据需创建", action="create_endpoint")
            return []

        logger.info(f"开始创建接口，数量: {len(endpoints)}", action="create_endpoint", count=len(endpoints))

        try:
            existing_keys = self._get_existing_keys(endpoints)
            logger.debug(
                f"已存在记录查询完成，重复数: {len(existing_keys)}",
                action="create_endpoint",
                existing_count=len(existing_keys),
            )
            new_data = [
                endpoint.model_dump()
                for endpoint in endpoints
                if (endpoint.space_id, endpoint.path, endpoint.method) not in existing_keys
            ]
            if not new_data:
                logger.warning("所有接口已存在，跳过插入", action="create_endpoint")
                return []
            skipped = len(endpoints) - len(new_data)
            if skipped:
                logger.info(f"跳过{skipped}个重复接口", action="create_endpoint", skipped=skipped)
            results = self.repo.bulk_create(new_data)
            logger.info(f"接口创建成功，数量: {len(results)}", action="create_endpoint", created=len(results))
            return results
        except Exception as e:
            logger.error(f"接口创建失败: {e}", action="create_endpoint", error=str(e))
            raise
