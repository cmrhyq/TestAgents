from pathlib import Path

from sqlalchemy.orm import Session

from src.core.errors import NotFoundError
from src.core.logging import get_logger
from src.data.models.report import Report
from src.data.repositories import ReportRepository
from src.data.services.base_service import BaseService
from src.data.services.test_result_service import TestResultService
from src.data.services.test_run_service import TestRunService

logger = get_logger(__name__)


class ReportService(BaseService[Report, ReportRepository]):
    def __init__(self, session: Session):
        super().__init__(session, ReportRepository(session))

    def create_report(self, report: Report) -> Report:
        """创建报告记录"""
        logger.info(
            f"创建报告: run_id={report.run_id}, format={report.format}",
            action="create_report",
            run_id=report.run_id,
            format=report.format,
        )
        return self.repo.add(report)

    def get_reports_by_run(self, run_id: int) -> list[Report]:
        """获取某次执行的所有报告"""
        return self.repo.get_by_run(run_id)

    def list_reports(self, run_id: int | None, page: int, page_size: int) -> tuple[list[tuple[Report, str]], int]:
        """分页查询报告列表，返回 ``(report, run_name)`` 元组与总数，避免逐条回查 TestRun。"""
        filters = []
        if run_id is not None:
            filters.append(Report.run_id == run_id)
        page_items, total = self.list(page, page_size, *filters, order_by=[Report.generated_at.desc()])

        run_ids = {report.run_id for report in page_items}
        runs = {}
        if run_ids:
            run_rows = TestRunService(self._session).get_runs_by_ids(list(run_ids))
            runs = {run.id: run for run in run_rows}

        return [(report, runs[report.run_id].name if report.run_id in runs else "") for report in page_items], total

    def get_report_by_format(self, run_id: int, report_format: str) -> Report | None:
        """获取某次执行指定格式的报告"""
        return self.repo.get_by_run_and_format(run_id, report_format)

    def get_detail(self, report_id: int):
        report = self.get(report_id)
        if report is None:
            raise NotFoundError("报告不存在")
        test_run = TestRunService(self._session).get(report.run_id)
        if test_run is None:
            raise NotFoundError("关联的测试运行不存在")
        results = TestResultService(self._session).get_results_by_run(report.run_id)
        return report, test_run, results

    def get_download_file(self, report_id: int) -> tuple[Report, Path]:
        report = self.get(report_id)
        if report is None:
            raise NotFoundError("报告不存在")
        file_path = Path(report.file_path)
        if not file_path.exists():
            raise NotFoundError("报告文件不存在")
        return report, file_path
