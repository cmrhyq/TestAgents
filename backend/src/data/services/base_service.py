from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy.orm import Session

from src.core.errors import NotFoundError
from src.data.models.base import Base
from src.data.repositories.base import BaseRepository

TModel = TypeVar("TModel", bound=Base)
TRepo = TypeVar("TRepo", bound=BaseRepository[Any])


class BaseService(Generic[TModel, TRepo]):
    """业务层通用 CRUD 契约。

    Service 负责业务规则与事务内的数据编排，Repository 只负责数据访问。
    提交事务由 API 的 ``get_db`` 或数据库上下文管理器负责，Service 不自持事务边界。
    """

    def __init__(self, session: Session, repository: TRepo) -> None:
        """绑定会话与仓储。

        Args:
            session: 调用方持有的会话，与仓储共用同一事务
            repository: 该服务操作的仓储实例
        """
        self._session = session
        self.repo = repository

    def get(self, record_id: int) -> TModel | None:
        """按主键取实体。

        Args:
            record_id: 主键值

        Returns:
            实体；不存在时返回 None
        """
        return self.repo.get_by_id(record_id)

    def get_or_raise(self, record_id: int, message: str = "记录不存在") -> TModel:
        """按主键取实体，不存在时抛异常。

        Args:
            record_id: 主键值
            message: 异常信息

        Returns:
            实体

        Raises:
            NotFoundError: 记录不存在
        """
        entity = self.get(record_id)
        if entity is None:
            raise NotFoundError(message)
        return entity

    def list(
        self,
        page: int = 1,
        page_size: int = 20,
        *filters: Any,
        order_by: Any = None,
    ) -> tuple[list[TModel], int]:
        """分页查询实体。

        Args:
            page: 页码，从 1 开始
            page_size: 每页条数
            *filters: 过滤条件表达式
            order_by: 排序表达式或表达式列表

        Returns:
            当前页实体列表与总数
        """
        return self.repo.paginate(page, page_size, *filters, order_by=order_by)

    def create(self, entity: TModel) -> TModel:
        """新增实体。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            entity: 待持久化的实体

        Returns:
            持久化后的实体，已带自增主键
        """
        return self.repo.add(entity)

    def update(self, record_id: int, **fields: Any) -> TModel:
        """按主键局部更新字段，值为 None 的项跳过。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            record_id: 主键值
            fields: 关键字形式的待更新字段名与值

        Returns:
            更新后的实体

        Raises:
            NotFoundError: 记录不存在
        """
        updated = self.repo.update_fields(record_id, **fields)
        if updated is None:
            raise NotFoundError("记录不存在")
        return updated

    def delete(self, record_id: int) -> None:
        """按主键删除实体。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            record_id: 主键值

        Raises:
            NotFoundError: 记录不存在
        """
        if not self.repo.delete_by_id(record_id):
            raise NotFoundError("记录不存在")
