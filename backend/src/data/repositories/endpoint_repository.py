from sqlalchemy import and_, literal, select
from sqlalchemy.orm import Session

from src.data.enum.workflow import DataStatus
from src.data.models.endpoint import Endpoint
from src.data.repositories.base import BaseRepository


class EndpointRepository(BaseRepository[Endpoint]):
    """API 定义表数据访问"""

    def __init__(self, session: Session) -> None:
        super().__init__(Endpoint, session)

    def check_duplicate(self, space_id: int, path: str, method: str) -> bool:
        """
        数据查重
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
        """批量查询：一次 SQL 替代 N 次循环查询"""
        stmt = select(Endpoint).where(
            and_(
                Endpoint.space_id.in_(space_ids),
                Endpoint.path.in_(paths),
                Endpoint.method.in_(methods),
            )
        )
        return list(self._session.scalars(stmt).all())

    def get_by_space(self, space_id: int, active_only: bool = True) -> list[Endpoint]:
        conditions = [Endpoint.space_id == space_id]
        if active_only:
            conditions.append(Endpoint.status == DataStatus.ENABLE.value)
        stmt = select(Endpoint).where(and_(*conditions))
        return list(self._session.scalars(stmt).all())

    def find_by_identity(self, space_id: int, path: str, method: str) -> list[Endpoint]:
        """按 (space_id, path, method) 查询全部匹配记录，供查重时排除自身。"""
        stmt = select(Endpoint).where(
            and_(
                Endpoint.space_id == space_id,
                Endpoint.path == path,
                Endpoint.method == method.upper(),
            )
        )
        return list(self._session.scalars(stmt).all())

    def get_active_by_ids(self, endpoint_ids: list[int]) -> list[Endpoint]:
        """按 ID 列表查询启用状态的接口"""
        stmt = select(Endpoint).where(
            and_(
                Endpoint.id.in_(endpoint_ids),
                Endpoint.status == DataStatus.ENABLE.value,
            )
        )
        return list(self._session.scalars(stmt).all())
