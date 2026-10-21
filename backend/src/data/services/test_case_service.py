from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.data.models.test_case import TestCase
from src.data.repositories import TestCaseRepository
from src.data.services.base_service import BaseService

logger = get_logger(__name__)


class TestCaseService(BaseService[TestCase, TestCaseRepository]):
    def __init__(self, session: Session):
        super().__init__(session, TestCaseRepository(session))

    def get_cases_by_run(self, run_id: int) -> list[TestCase]:
        """获取某次执行的所有用例"""
        return self.repo.get_by_run(run_id)

    def get_case_by_id(self, case_id: int) -> TestCase | None:
        """按主键获取用例"""
        return self.repo.get_by_id(case_id)

    def get_active_cases_by_run(self, run_id: int) -> list[TestCase]:
        """获取某次执行中启用状态的用例"""
        return self.repo.get_by_run_and_status(run_id, 1)

    def count_by_run(self, run_id: int) -> int:
        """统计某次执行的用例数"""
        return self.repo.count_by_run(run_id)

    def add_case(self, case: TestCase) -> TestCase:
        return self.create(case)
