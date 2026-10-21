from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from src.data.models.report import Report
from src.data.repositories.base import BaseRepository, RunScopedRepositoryMixin


class ReportRepository(RunScopedRepositoryMixin[Report], BaseRepository[Report]):
    """报告记录表数据访问"""

    def __init__(self, session: Session) -> None:
        super().__init__(Report, session)

    def get_by_run_and_format(self, run_id: int, report_format: str) -> Report | None:
        stmt = select(Report).where(and_(Report.run_id == run_id, Report.format == report_format))
        return self._session.scalar(stmt)
