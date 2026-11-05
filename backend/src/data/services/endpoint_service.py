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
    """接口业务逻辑。

    接口以 ``(space_id, path, method)`` 唯一；结构类字段以 JSON 字符串入库，
    ``method`` 统一存大写。
    """

    def __init__(self, session: Session):
        """绑定会话与接口仓储。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(session, EndpointRepository(session))

    def create_one(self, data: EndpointCreate) -> Endpoint:
        """创建单个接口，结构字段序列化为 JSON，``method`` 转大写。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            data: 接口创建参数

        Returns:
            新建的接口实体

        Raises:
            ValidationError: 未关联空间
            ConflictError: 同空间下路径与方法已存在
        """
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
        """按空间、方法与关键字分页查询接口，不按状态过滤。

        Args:
            space_id: 空间主键；None 表示全部空间
            method: HTTP 方法，内部转大写比较；空值表示不过滤
            keyword: 模糊匹配名称、路径、摘要与方法；空值表示不过滤
            page: 页码，从 1 开始
            page_size: 每页条数

        Returns:
            当前页接口列表与总数
        """
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
        """局部更新接口，改动路径或方法时校验唯一性。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            endpoint_id: 接口主键
            fields: 待更新字段，结构字段可为 dict 或 list

        Returns:
            更新后的接口

        Raises:
            ConflictError: 新的 ``(path, method)`` 与同空间其他接口冲突
            NotFoundError: 接口不存在
        """
        if "path" in fields or "method" in fields:
            current = self.get_or_raise(endpoint_id, "接口不存在")
            new_path = fields.get("path", current.path)
            new_method = self._normalize_method(fields.get("method", current.method))
            duplicates = self.repo.find_by_identity(current.space_id, new_path, new_method)
            if any(dup.id != endpoint_id for dup in duplicates):
                raise ConflictError(f"接口已存在: {new_method} {new_path}")
        for field in ("tags", "params", "headers", "body", "responses", "security"):
            if isinstance(fields.get(field), (list, dict)):
                fields[field] = json.dumps(fields[field], ensure_ascii=False)
        if fields.get("method"):
            fields["method"] = self._normalize_method(fields["method"])
        return self.update(endpoint_id, **fields)

    @staticmethod
    def _normalize_method(value) -> str:
        """把 HTTP 方法统一为入库用的大写字符串。

        ``fields`` 中的 method 可能来自枚举 ``HttpMethod``，直接 ``str()`` 会得到
        ``"HttpMethod.GET"`` 这类非法值，需先取 ``value``。

        Args:
            value: HTTP 方法，字符串或 ``HttpMethod`` 枚举

        Returns:
            大写的 HTTP 方法字符串
        """
        return str(getattr(value, "value", value)).upper()

    def get_active_by_ids(self, endpoint_ids: list[int]) -> list[Endpoint]:
        """按主键列表取启用接口。

        Args:
            endpoint_ids: 接口主键列表

        Returns:
            启用的接口列表，已停用的主键被忽略
        """
        return self.repo.get_active_by_ids(endpoint_ids)

    def list_active(self, space_id: int) -> list[Endpoint]:
        """列出空间下启用的接口。

        Args:
            space_id: 空间主键

        Returns:
            启用的接口列表
        """
        return self.repo.get_by_space(space_id, active_only=True)

    def _get_existing_keys(self, endpoint_list: list[EndpointCreate]) -> set:
        """批量查询已存在的 ``(space_id, path, method)`` 组合，单条 SQL 完成。

        Args:
            endpoint_list: 待检查的接口创建参数

        Returns:
            已存在的 ``(space_id, path, method)`` 集合
        """
        space_ids = {endpoint.space_id for endpoint in endpoint_list}
        paths = {endpoint.path for endpoint in endpoint_list}
        methods = {endpoint.method for endpoint in endpoint_list}
        existing = self.repo.bulk_query(space_ids, paths, methods)
        return {(item.space_id, item.path, item.method) for item in existing}

    def create_endpoint(self, endpoints: list[EndpointCreate]) -> list[Endpoint]:
        """按 ``(space_id, path, method)`` 去重后批量创建接口。

        与 ``create_one`` 不同，本方法不序列化结构字段、不转写 ``method``，
        入参需已符合入库格式。

        副作用：写库（未提交），需调用方提交事务；失败时记录日志并原样抛出。

        Args:
            endpoints: 接口创建参数列表

        Returns:
            实际新建的接口列表；全部重复或入参为空时返回空列表

        Raises:
            Exception: 批量写入失败时向上抛出，事务由调用方回滚
        """
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
