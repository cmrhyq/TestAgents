import json

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.core.errors import ConflictError
from src.core.logging import get_logger
from src.data.models import Environment
from src.data.repositories import EnvironmentRepository
from src.data.schemas.environment import EnvironmentCreate
from src.data.services.base_service import BaseService

logger = get_logger(__name__)


class EnvironmentService(BaseService[Environment, EnvironmentRepository]):
    def __init__(self, session: Session):
        super().__init__(session, EnvironmentRepository(session))

    def create_environment(self, data: EnvironmentCreate) -> Environment:
        if self.repo.get_by_space_and_name(data.space_id, data.name) is not None:
            raise ConflictError(f"环境已存在: {data.name}")
        values = data.model_dump()
        if isinstance(values.get("variables"), dict):
            values["variables"] = json.dumps(values["variables"], ensure_ascii=False)
        return self.create(Environment(**values))

    def list_environments(self, space_id: int | None, keyword: str | None, page: int, page_size: int):
        filters = []
        if space_id is not None:
            filters.append(Environment.space_id == space_id)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(Environment.name.ilike(pattern), Environment.description.ilike(pattern)))
        return self.list(page, page_size, *filters)

    def list_by_space(self, space_id: int) -> list[Environment]:
        """列出空间下全部启用环境（供 Agent 工具与环境选择器使用）。"""
        items, _ = self.list(1, 200, Environment.space_id == space_id, Environment.status == 1)
        return items

    def get_by_id(self, env_id: int) -> Environment | None:
        """按 ID 取环境（工具层拼 base_url 与生产环境闸门用）。"""
        return self.get(env_id)

    def update_environment(self, env_id: int, fields: dict) -> Environment:
        if "name" in fields:
            current = self.get_or_raise(env_id, "环境不存在")
            existing = self.repo.get_by_space_and_name(current.space_id, fields["name"])
            if existing is not None and existing.id != env_id:
                raise ConflictError(f"环境已存在: {fields['name']}")
        if isinstance(fields.get("variables"), dict):
            fields["variables"] = json.dumps(fields["variables"], ensure_ascii=False)
        return self.update(env_id, **fields)

    def _get_existing_keys(self, env_list: list[EnvironmentCreate]) -> set:
        """批量查询已存在的 (space_id, name) 组合"""
        space_ids = {env.space_id for env in env_list}
        names = {env.name for env in env_list}
        existing = self.repo.bulk_query(space_ids, names)
        return {(item.space_id, item.name) for item in existing}

    def create_env(self, env_list: list[EnvironmentCreate]) -> list[Environment]:
        """
        去重批量创建环境
        """
        if len(env_list) == 0:
            logger.warning("无环境数据需创建", action="create_env")
            return []

        logger.info(f"开始创建环境，数量: {len(env_list)}", action="create_env", count=len(env_list))
        try:
            existing_keys = self._get_existing_keys(env_list)
            new_data = [env.model_dump() for env in env_list if (env.space_id, env.name) not in existing_keys]
            if not new_data:
                logger.warning("所有环境已存在，跳过插入", action="create_env")
                return []
            skipped = len(env_list) - len(new_data)
            if skipped:
                logger.info(f"跳过{skipped}个重复环境", action="create_env", skipped=skipped)
            results = self.repo.bulk_create(new_data)
            logger.info(f"环境创建成功，数量: {len(results)}", action="create_env", created=len(results))
            return results
        except Exception as e:
            logger.error(f"环境创建失败: {e}", action="create_env", error=str(e))
            raise
