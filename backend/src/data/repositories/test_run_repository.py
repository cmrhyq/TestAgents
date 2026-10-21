from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.models.test_run import TestRun
from src.data.repositories.base import BaseRepository


class TestRunRepository(BaseRepository[TestRun]):
    """执行批次表数据访问"""

    def __init__(self, session: Session) -> None:
        super().__init__(TestRun, session)

    def get_by_space(self, space_id: int, limit: int = 50) -> list[TestRun]:
        stmt = select(TestRun).where(TestRun.space_id == space_id).order_by(TestRun.created_at.desc()).limit(limit)
        return list(self._session.scalars(stmt).all())

    def get_by_ids(self, run_ids: list[int]) -> list[TestRun]:
        """按 ID 列表批量查询执行批次。"""
        if not run_ids:
            return []
        stmt = select(TestRun).where(TestRun.id.in_(run_ids))
        return list(self._session.scalars(stmt).all())
