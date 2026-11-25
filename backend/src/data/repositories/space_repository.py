from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from src.data.models.skill import Skill
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
        ``skill`` 是例外：它按 ``space_id`` 归属但**刻意不建外键**（``builtin``
        作用域的行 ``space_id`` 为 NULL，且该表不属于任何 ORM 关系），
        所以这里单独做一次批量删除，否则空间级 skill 行会残留成孤儿。

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
                # 以下三个不在原加载列表里，级联时会懒加载；显式预加载避免 N+1
                selectinload(Space.conversations),
                selectinload(Space.memories),
                selectinload(Space.documents),
            )
        )
        space = self._session.scalar(stmt)
        if space is None:
            return False

        # 先清空间级 skill 注册行（无外键，删空后 builtin 行不受影响）
        self._session.execute(delete(Skill).where(Skill.space_id == space_id))

        self._session.delete(space)
        self._session.flush()
        return True
