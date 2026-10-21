from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.data.models.space import Space
from src.data.repositories.base import BaseRepository


class SpaceRepository(BaseRepository[Space]):
    """空间表数据访问"""

    def __init__(self, session: Session) -> None:
        super().__init__(Space, session)

    def get_by_name(self, name: str) -> Space | None:
        stmt = select(Space).where(Space.name == name)
        return self._session.scalar(stmt)

    def delete_cascade(self, space_id: int) -> bool:
        """级联删除空间及其关联的 environments、endpoints、test_runs 等数据。"""
        stmt = (
            select(Space)
            .where(Space.id == space_id)
            .options(
                selectinload(Space.endpoints),
                selectinload(Space.environments),
                selectinload(Space.test_runs),
            )
        )
        space = self._session.scalar(stmt)
        if space is None:
            return False
        self._session.delete(space)
        self._session.flush()
        return True
