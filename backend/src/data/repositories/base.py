from typing import Any, Generic, TypeVar, cast

from sqlalchemy import ColumnElement, func, literal, select
from sqlalchemy.orm import Session

from src.data.models.base import Base, local_now

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """通用 CRUD 基类。

    所有写操作只 ``flush``，不 ``commit``；事务边界由调用方（通常是用例层）提交或回滚。
    """

    def __init__(self, model_class: type[T], session: Session) -> None:
        """绑定模型类与会话。

        Args:
            model_class: 该仓储负责的 ORM 模型
            session: 调用方持有的会话，生命周期由调用方管理
        """
        self._model = model_class
        self._session = session

    def get_by_id(self, record_id: int) -> T | None:
        """按主键取单条记录。

        Args:
            record_id: 主键值

        Returns:
            实体；不存在时返回 None
        """
        return self._session.get(self._model, record_id)

    def get_all(self, limit: int = 1000, offset: int = 0) -> list[T]:
        """按固定上限取记录列表。

        Args:
            limit: 最多返回条数
            offset: 跳过条数

        Returns:
            实体列表，不排序
        """
        stmt = select(self._model).limit(limit).offset(offset)
        return list(self._session.scalars(stmt).all())

    def add(self, entity: T) -> T:
        """新增一条记录，``flush`` 后返回同一实体。

        副作用：写库（未提交），主键在 `flush` 后可用。

        Args:
            entity: 待持久化的实体

        Returns:
            传入的实体，已带自增主键
        """
        self._session.add(entity)
        self._session.flush()
        return entity

    def add_many(self, entities: list[T]) -> list[T]:
        """批量新增，``flush`` 一次。

        副作用：写库（未提交）。

        Args:
            entities: 待持久化的实体列表

        Returns:
            传入的实体列表
        """
        self._session.add_all(entities)
        self._session.flush()
        return entities

    def update_entity(self, entity: T) -> T:
        """合并并更新托管实体，``flush`` 后返回合并结果。

        副作用：写库（未提交）。

        Args:
            entity: 含新值的实体，可为分离态

        Returns:
            会话内的托管实体
        """
        merged = self._session.merge(entity)
        self._session.flush()
        return merged

    def update_fields(self, record_id: int, **fields: Any) -> T | None:
        """按主键局部更新字段，值为 None 的项会被跳过。

        副作用：写库（未提交）；模型含 ``updated_at`` 时同步刷新该字段。

        Args:
            record_id: 主键值
            fields: 关键字形式的待更新字段名与值

        Returns:
            更新后的实体；记录不存在时返回 None
        """
        entity = self.get_by_id(record_id)
        if entity is None:
            return None
        for key, value in fields.items():
            if value is None:
                continue
            setattr(entity, key, value)
        if hasattr(entity, "updated_at"):
            entity.updated_at = local_now()
        self._session.flush()
        return entity

    def delete_by_id(self, record_id: int) -> bool:
        """按主键删除记录。

        副作用：写库（未提交），删除在事务提交后才生效。

        Args:
            record_id: 主键值

        Returns:
            是否删除了记录；不存在时为 False
        """
        entity = self.get_by_id(record_id)
        if entity is None:
            return False
        self._session.delete(entity)
        self._session.flush()
        return True

    def bulk_create(self, objects: list[dict]) -> list[T]:
        """按字典批量构造实体并写入，逐条 `refresh` 回填数据库默认值。

        副作用：写库（未提交）并触发额外查询。

        Args:
            objects: 模型字段字典列表

        Returns:
            新建的实体列表，顺序与入参一致
        """
        db_objects = [self._model(**obj) for obj in objects]
        self._session.add_all(db_objects)
        self._session.flush()
        for obj in db_objects:
            self._session.refresh(obj)
        return db_objects

    def count(self) -> int:
        """返回全表记录数。"""
        stmt = select(func.count()).select_from(self._model)
        return self._session.scalar(stmt) or 0

    def exists(self, record_id: int) -> bool:
        """按主键判断记录是否存在，避免加载完整实体。"""
        pk = cast(Any, self._model).id
        stmt = select(literal(1)).where(pk == record_id).limit(1)
        return self._session.scalar(stmt) is not None

    def paginate(
        self,
        page: int = 1,
        page_size: int = 20,
        *filters: ColumnElement[bool],
        order_by: Any = None,
    ) -> tuple[list[T], int]:
        """分页查询，返回 ``(items, total)``。

        ``order_by`` 接受单个排序表达式或表达式列表（如 ``[Model.created_at.desc()]``）；
        不传时保持数据库默认顺序。``page`` 与 ``page_size`` 小于 1 时按 1 处理。

        Args:
            page: 页码，从 1 开始
            page_size: 每页条数
            *filters: 作用于统计与列表查询的过滤条件
            order_by: 排序表达式或表达式列表

        Returns:
            当前页实体列表与满足过滤条件的总数
        """
        page = max(page, 1)
        page_size = max(page_size, 1)
        offset = (page - 1) * page_size

        count_stmt = select(func.count()).select_from(self._model)
        list_stmt = select(self._model)
        if filters:
            count_stmt = count_stmt.where(*filters)
            list_stmt = list_stmt.where(*filters)
        if order_by is not None:
            if isinstance(order_by, (list, tuple)):
                list_stmt = list_stmt.order_by(*order_by)
            else:
                list_stmt = list_stmt.order_by(order_by)

        total = self._session.scalar(count_stmt) or 0
        items = list(self._session.scalars(list_stmt.limit(page_size).offset(offset)).all())
        return items, total


class RunScopedRepositoryMixin(Generic[T]):
    """为含 ``run_id`` 外键的表提供按执行批次查询的通用方法。

    依赖宿主 Repository（``BaseRepository[T]`` 子类）提供的 ``_model`` 与
    ``_session`` 属性，模型需包含 ``run_id`` 列。
    """

    _model: type[T]
    _session: Session

    def get_by_run(self, run_id: int) -> list[T]:
        """返回指定批次下的全部记录。"""
        stmt = select(self._model).where(cast(Any, self._model).run_id == run_id)
        return list(self._session.scalars(stmt).all())

    def count_by_run(self, run_id: int) -> int:
        """统计指定批次下的记录数。"""
        stmt = select(func.count()).select_from(self._model).where(cast(Any, self._model).run_id == run_id)
        return self._session.scalar(stmt) or 0
