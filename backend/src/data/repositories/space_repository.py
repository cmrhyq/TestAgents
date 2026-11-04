from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.data.models.space import Space
from src.data.repositories.base import BaseRepository


class SpaceRepository(BaseRepository[Space]):
    """空间表数据访问。"""

    def __init__(self, session: Session) -> None:
        """绑定空间模型。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(Space, session)

    def get_by_name(self, name: str) -> Space | None:
        """按名称精确查询空间。

        Args:
            name: 空间名，需完全匹配

        Returns:
            空间实体；不存在时返回 None
        """
        stmt = select(Space).where(Space.name == name)
        return self._session.scalar(stmt)

    def delete_cascade(self, space_id: int) -> bool:
        """级联删除空间及其关联数据。

        依赖模型关系的 cascade 配置显式加载子对象后才删除，不经数据库外键级联。
        副作用：写库（未提交），需调用方提交事务。

        Args:
            space_id: 空间主键

        Returns:
            是否删除；空间不存在时返回 False
        """
        stmt = (
            select(Space)
            .where(Space.id == space_id)
            .options(
                selectinload(Space.endpoints),
                selectinload(Space.environments),
                selectinload(Space.agent_runs),
            )
        )
        space = self._session.scalar(stmt)
        if space is None:
            return False
        self._session.delete(space)
        self._session.flush()
        return True
