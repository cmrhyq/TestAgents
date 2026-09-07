from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.models.environment import Environment
from src.data.repositories.base import BaseRepository


class EnvironmentRepository(BaseRepository[Environment]):
    """环境表数据访问"""

    def __init__(self, session: Session) -> None:
        super().__init__(Environment, session)

    def get_by_name(self, name: str) -> Environment | None:
        stmt = select(Environment).where(Environment.name == name)
        return self._session.scalar(stmt)

    def get_default_by_space(self, space_id: int) -> Environment | None:
        """查询空间下的默认环境（is_default=1），无默认时返回最新一个环境。"""
        stmt = (
            select(Environment)
            .where(Environment.space_id == space_id, Environment.is_default == 1, Environment.status == 1)
            .limit(1)
        )
        env = self._session.scalar(stmt)
        if env is not None:
            return env
        fallback = select(Environment).where(Environment.space_id == space_id).order_by(Environment.id.desc()).limit(1)
        return self._session.scalar(fallback)

    def get_by_space_and_name(self, space_id: int, name: str) -> Environment | None:
        stmt = select(Environment).where(Environment.space_id == space_id, Environment.name == name)
        return self._session.scalar(stmt)

    def bulk_query(self, space_ids: set, names: set) -> list[Environment]:
        """批量查询：一次 SQL 替代 N 次循环查询"""
        stmt = select(Environment).where(Environment.space_id.in_(space_ids), Environment.name.in_(names))
        return list(self._session.scalars(stmt).all())
