from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.data.models.test_result import TestResult
from src.data.repositories.base import BaseRepository, RunScopedRepositoryMixin


class TestResultRepository(RunScopedRepositoryMixin[TestResult], BaseRepository[TestResult]):
    """测试结果表数据访问"""

    def __init__(self, session: Session) -> None:
        super().__init__(TestResult, session)

    def get_by_test_case(self, test_case_id: int) -> list[TestResult]:
        stmt = select(TestResult).where(TestResult.test_case_id == test_case_id)
        return list(self._session.scalars(stmt).all())

    def get_by_status(self, run_id: int, status: str) -> list[TestResult]:
        stmt = select(TestResult).where(and_(TestResult.run_id == run_id, TestResult.status == status))
        return list(self._session.scalars(stmt).all())

    def get_failed_results(self, run_id: int) -> list[TestResult]:
        stmt = select(TestResult).where(and_(TestResult.run_id == run_id, TestResult.status.in_(["failed", "error"])))
        return list(self._session.scalars(stmt).all())

    def count_by_status(self, run_id: int, status: str) -> int:
        stmt = (
            select(func.count())
            .select_from(TestResult)
            .where(and_(TestResult.run_id == run_id, TestResult.status == status))
        )
        return self._session.scalar(stmt) or 0
