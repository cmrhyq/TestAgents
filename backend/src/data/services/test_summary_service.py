from __future__ import annotations

from sqlalchemy.orm import Session

from src.data.models.test_summary import TestSummary
from src.data.repositories import TestSummaryRepository
from src.data.services.base_service import BaseService


class TestSummaryService(BaseService[TestSummary, TestSummaryRepository]):
    """测试摘要的 upsert 业务入口。"""

    def __init__(self, session: Session) -> None:
        super().__init__(session, TestSummaryRepository(session))

    def get_by_run(self, run_id: int) -> TestSummary | None:
        return self.repo.get_by_run(run_id)

    def create_or_update(self, run_id: int, **values) -> TestSummary:
        existing = self.get_by_run(run_id)
        if existing is not None:
            return self.update(existing.id, **values)
        return self.create(TestSummary(run_id=run_id, **values))
