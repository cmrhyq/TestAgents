from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from src.data.models.report import Report
from src.data.repositories.base import BaseRepository, RunScopedRepositoryMixin


class ReportRepository(RunScopedRepositoryMixin[Report], BaseRepository[Report]):
    """报告记录表数据访问。"""

    def __init__(self, session: Session) -> None:
        """绑定报告模型。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(Report, session)

    def get_by_run_and_format(self, run_id: int, report_format: str) -> Report | None:
        """按执行记录与报告格式取唯一报告行。

        Args:
            run_id: 执行记录主键
            report_format: 报告格式标识

        Returns:
            报告实体；不存在时返回 None
        """
        stmt = select(Report).where(and_(Report.run_id == run_id, Report.format == report_format))
        return self._session.scalar(stmt)

    def get_by_run_ids(self, run_ids: list[int]) -> list[Report]:
        """按执行记录批量取报告行。

        清理任务需先取 ``file_path`` 删除磁盘文件，再删除数据库行。

        Args:
            run_ids: 执行记录主键列表

        Returns:
            报告行列表；入参为空时返回空列表
        """
        if not run_ids:
            return []
        stmt = select(Report).where(Report.run_id.in_(run_ids))
        return list(self._session.scalars(stmt).all())

    def delete_by_run_ids(self, run_ids: list[int]) -> int:
        """按执行记录批量删除报告行，走批量 DELETE。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            run_ids: 执行记录主键列表

        Returns:
            删除行数；入参为空时返回 0
        """
        if not run_ids:
            return 0
        result = self._session.execute(delete(Report).where(Report.run_id.in_(run_ids)))
        return int(result.rowcount or 0)

