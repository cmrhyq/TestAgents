from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from src.data.models.test_case import TestCase
from src.data.repositories.base import BaseRepository, RunScopedRepositoryMixin


class TestCaseRepository(RunScopedRepositoryMixin[TestCase], BaseRepository[TestCase]):
    """测试用例表数据访问"""

    def __init__(self, session: Session) -> None:
        super().__init__(TestCase, session)

    def get_by_run_and_status(self, run_id: int, status: int) -> list[TestCase]:
        stmt = select(TestCase).where(TestCase.run_id == run_id, TestCase.status == status)
        return list(self._session.scalars(stmt).all())

    def get_by_case_id(self, case_id: str) -> TestCase | None:
        stmt = select(TestCase).where(TestCase.case_id == case_id)
        return self._session.scalar(stmt)

    def get_by_scenario(self, run_id: int, scenario_type: str) -> list[TestCase]:
        stmt = select(TestCase).where(and_(TestCase.run_id == run_id, TestCase.scenario_type == scenario_type))
        return list(self._session.scalars(stmt).all())
