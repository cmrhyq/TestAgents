from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.models.environment import Environment
from src.data.repositories.base import BaseRepository


class EnvironmentRepository(BaseRepository[Environment]):
    """环境表数据访问。"""

    def __init__(self, session: Session) -> None:
        """绑定环境模型。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(Environment, session)

    def get_by_name(self, name: str) -> Environment | None:
        """按名称精确查询环境。

        Args:
            name: 环境名

        Returns:
            环境实体；不存在时返回 None
        """
        stmt = select(Environment).where(Environment.name == name)
        return self._session.scalar(stmt)

    def get_default_by_space(self, space_id: int) -> Environment | None:
        """查询空间下的默认环境。

        取 ``is_default=1`` 且启用的环境；没有时回退到该空间 id 最大的环境。

        Args:
            space_id: 空间主键

        Returns:
            环境实体；空间下无任何环境时返回 None
        """
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
        """按空间与名称查询唯一环境。

        Args:
            space_id: 空间主键
            name: 环境名

        Returns:
            环境实体；不存在时返回 None
        """
        stmt = select(Environment).where(Environment.space_id == space_id, Environment.name == name)
        return self._session.scalar(stmt)

    def bulk_query(self, space_ids: set, names: set) -> list[Environment]:
        """按空间集合与名称集合批量查询，单条 SQL 完成。

        Args:
            space_ids: 空间主键集合
            names: 环境名集合

        Returns:
            匹配的环境列表；集合为空时返回空列表
        """
        stmt = select(Environment).where(Environment.space_id.in_(space_ids), Environment.name.in_(names))
        return list(self._session.scalars(stmt).all())
