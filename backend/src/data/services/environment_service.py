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
    """环境业务逻辑。

    环境按空间隔离，同空间内名称唯一；``variables`` 以 JSON 字符串入库。
    """

    def __init__(self, session: Session):
        """绑定会话与环境仓储。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(session, EnvironmentRepository(session))

    def create_environment(self, data: EnvironmentCreate) -> Environment:
        """创建单个环境，``variables`` 为字典时序列化为 JSON 字符串。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            data: 环境创建参数

        Returns:
            新建的环境实体

        Raises:
            ConflictError: 同空间下名称已存在
        """
        if self.repo.get_by_space_and_name(data.space_id, data.name) is not None:
            raise ConflictError(f"环境已存在: {data.name}")
        values = data.model_dump()
        if isinstance(values.get("variables"), dict):
            values["variables"] = json.dumps(values["variables"], ensure_ascii=False)
        return self.create(Environment(**values))

    def list_environments(self, space_id: int | None, keyword: str | None, page: int, page_size: int):
        """按空间与名称/描述关键字分页查询环境，不过滤状态。

        Args:
            space_id: 空间主键；None 表示全部空间
            keyword: 模糊匹配名称与描述；空值表示不过滤
            page: 页码，从 1 开始
            page_size: 每页条数

        Returns:
            当前页环境列表与总数
        """
        filters = []
        if space_id is not None:
            filters.append(Environment.space_id == space_id)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(Environment.name.ilike(pattern), Environment.description.ilike(pattern)))
        return self.list(page, page_size, *filters)

    def list_by_space(self, space_id: int) -> list[Environment]:
        """列出空间下全部启用环境，供 Agent 工具与环境选择器使用。

        Args:
            space_id: 空间主键

        Returns:
            环境列表，最多 200 条
        """
        items, _ = self.list(1, 200, Environment.space_id == space_id, Environment.status == 1)
        return items

    def get_by_id(self, env_id: int) -> Environment | None:
        """按主键取环境，供工具层拼 ``base_url`` 与生产环境校验使用。

        Args:
            env_id: 环境主键

        Returns:
            环境实体；不存在时返回 None
        """
        return self.get(env_id)

    def update_environment(self, env_id: int, fields: dict) -> Environment:
        """局部更新环境，改名时校验同空间内冲突。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            env_id: 环境主键
            fields: 待更新字段，``variables`` 为字典时序列化为 JSON 字符串

        Returns:
            更新后的环境

        Raises:
            ConflictError: 新名称已被同空间的其他环境占用
            NotFoundError: 环境不存在
        """
        if "name" in fields:
            current = self.get_or_raise(env_id, "环境不存在")
            existing = self.repo.get_by_space_and_name(current.space_id, fields["name"])
            if existing is not None and existing.id != env_id:
                raise ConflictError(f"环境已存在: {fields['name']}")
        if isinstance(fields.get("variables"), dict):
            fields["variables"] = json.dumps(fields["variables"], ensure_ascii=False)
        return self.update(env_id, **fields)

    def _get_existing_keys(self, env_list: list[EnvironmentCreate]) -> set:
        """批量查询已存在的 ``(space_id, name)`` 组合，单条 SQL 完成。

        Args:
            env_list: 待检查的环境创建参数

        Returns:
            已存在的 ``(space_id, name)`` 集合
        """
        space_ids = {env.space_id for env in env_list}
        names = {env.name for env in env_list}
        existing = self.repo.bulk_query(space_ids, names)
        return {(item.space_id, item.name) for item in existing}

    def create_env(self, env_list: list[EnvironmentCreate]) -> list[Environment]:
        """按 ``(space_id, name)`` 去重后批量创建环境。

        副作用：写库（未提交），需调用方提交事务；失败时记录日志并原样抛出。

        Args:
            env_list: 环境创建参数列表

        Returns:
            实际新建的环境列表；全部重复或入参为空时返回空列表

        Raises:
            Exception: 批量写入失败时向上抛出，事务由调用方回滚
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
