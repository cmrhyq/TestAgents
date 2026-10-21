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

    Service 负责业务规则和事务内的数据编排；Repository 只负责数据访问。
    提交事务仍由 API 的 ``get_db`` 或数据库上下文管理器负责。
    """

    def __init__(self, session: Session, repository: TRepo) -> None:
        self._session = session
        self.repo = repository

    def get(self, record_id: int) -> TModel | None:
        return self.repo.get_by_id(record_id)

    def get_or_raise(self, record_id: int, message: str = "记录不存在") -> TModel:
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
        return self.repo.paginate(page, page_size, *filters, order_by=order_by)

    def create(self, entity: TModel) -> TModel:
        return self.repo.add(entity)

    def update(self, record_id: int, **fields: Any) -> TModel:
        updated = self.repo.update_fields(record_id, **fields)
        if updated is None:
            raise NotFoundError("记录不存在")
        return updated

    def delete(self, record_id: int) -> None:
        if not self.repo.delete_by_id(record_id):
            raise NotFoundError("记录不存在")
