from sqlalchemy import and_, literal, select
from sqlalchemy.orm import Session

from src.data.enum.workflow import DataStatus
from src.data.models.endpoint import Endpoint
from src.data.repositories.base import BaseRepository


class EndpointRepository(BaseRepository[Endpoint]):
    """接口定义表数据访问。"""

    def __init__(self, session: Session) -> None:
        """绑定接口模型。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(Endpoint, session)

    def check_duplicate(self, space_id: int, path: str, method: str) -> bool:
        """判断同一空间内是否已存在相同路径与方法的接口。

        Args:
            space_id: 空间主键
            path: 接口路径
            method: HTTP 方法，内部统一转大写后比较

        Returns:
            已存在返回 True
        """
        stmt = (
            select(literal(1))
            .select_from(Endpoint)
            .where(
                and_(
                    Endpoint.space_id == space_id,
                    Endpoint.path == path,
                    Endpoint.method == method.upper(),
                )
            )
            .limit(1)
        )
        return self._session.scalar(stmt) is not None

    def bulk_query(self, space_ids: set, paths: set, methods: set) -> list[Endpoint]:
        """按空间、路径、方法三个集合批量查询，单条 SQL 完成。

        Args:
            space_ids: 空间主键集合
            paths: 接口路径集合
            methods: HTTP 方法集合，使用调用方传入的大小写

        Returns:
            匹配的接口列表
        """
        stmt = select(Endpoint).where(
            and_(
                Endpoint.space_id.in_(space_ids),
                Endpoint.path.in_(paths),
                Endpoint.method.in_(methods),
            )
        )
        return list(self._session.scalars(stmt).all())

    def get_by_space(self, space_id: int, active_only: bool = True) -> list[Endpoint]:
        """查询空间下的接口。

        Args:
            space_id: 空间主键
            active_only: 为 True 时只返回启用状态的接口

        Returns:
            接口列表，不排序
        """
        conditions = [Endpoint.space_id == space_id]
        if active_only:
            conditions.append(Endpoint.status == DataStatus.ENABLE.value)
        stmt = select(Endpoint).where(and_(*conditions))
        return list(self._session.scalars(stmt).all())

    def find_by_identity(self, space_id: int, path: str, method: str) -> list[Endpoint]:
        """按空间、路径、方法查询全部匹配记录，供查重时排除自身。

        Args:
            space_id: 空间主键
            path: 接口路径
            method: HTTP 方法，内部统一转大写后比较

        Returns:
            匹配的接口列表
        """
        stmt = select(Endpoint).where(
            and_(
                Endpoint.space_id == space_id,
                Endpoint.path == path,
                Endpoint.method == method.upper(),
            )
        )
        return list(self._session.scalars(stmt).all())

    def get_active_by_ids(self, endpoint_ids: list[int]) -> list[Endpoint]:
        """按主键列表取启用状态的接口。

        Args:
            endpoint_ids: 接口主键列表

        Returns:
            启用的接口列表；已停用或不存在的主键被忽略
        """
        stmt = select(Endpoint).where(
            and_(
                Endpoint.id.in_(endpoint_ids),
                Endpoint.status == DataStatus.ENABLE.value,
            )
        )
        return list(self._session.scalars(stmt).all())
