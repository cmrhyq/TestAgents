from sqlalchemy import and_, delete, select
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

    def get_by_run_ids(self, run_ids: list[int]) -> list[Report]:
        """按执行 ID 批量查报告行（清理任务用，需先取 file_path 再删）。"""
        if not run_ids:
            return []
        stmt = select(Report).where(Report.run_id.in_(run_ids))
        return list(self._session.scalars(stmt).all())

    def delete_by_run_ids(self, run_ids: list[int]) -> int:
        """按执行 ID 批量删除报告行，返回删除行数。"""
        if not run_ids:
            return 0
        result = self._session.execute(delete(Report).where(Report.run_id.in_(run_ids)))
        return int(result.rowcount or 0)

