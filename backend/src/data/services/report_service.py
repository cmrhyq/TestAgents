from pathlib import Path

from sqlalchemy.orm import Session

from src.core.errors import NotFoundError
from src.core.logging import get_logger
from src.data.models.agent_run import AgentRun
from src.data.models.agent_tool_call import AgentToolCall
from src.data.models.report import Report
from src.data.repositories import ReportRepository
from src.data.services.agent_run_service import AgentRunService
from src.data.services.agent_tool_call_service import AgentToolCallService
from src.data.services.base_service import BaseService

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
        """分页查询报告列表，返回 ``(report, run_title)`` 元组与总数。

        一次分页 + 一次批量回查，避免逐条取执行记录名。
        """
        filters = []
        if run_id is not None:
            filters.append(Report.run_id == run_id)
        page_items, total = self.list(page, page_size, *filters, order_by=[Report.generated_at.desc()])

        run_ids = {report.run_id for report in page_items}
        runs = {}
        if run_ids:
            run_rows = AgentRunService(self._session).get_runs_by_ids(list(run_ids))
            runs = {run.id: run for run in run_rows}

        return [(report, runs[report.run_id].title if report.run_id in runs else "") for report in page_items], total

    def get_report_by_format(self, run_id: int, report_format: str) -> Report | None:
        """获取某次执行指定格式的报告"""
        return self.repo.get_by_run_and_format(run_id, report_format)

    def get_detail(self, report_id: int) -> tuple[Report, AgentRun, list[AgentToolCall]]:
        """返回 ``(报告, 关联执行记录, 该次执行的工具调用留痕)``。

        第三个元素默认不含响应体（见 ``AgentToolCallService.list_by_run``），
        详情页要看响应体走单条接口。
        """
        report = self.get(report_id)
        if report is None:
            raise NotFoundError("报告不存在")
        run = AgentRunService(self._session).get(report.run_id)
        if run is None:
            raise NotFoundError("关联的执行记录不存在")
        tool_calls = AgentToolCallService(self._session).list_by_run(report.run_id)
        return report, run, tool_calls

    def get_download_file(self, report_id: int) -> tuple[Report, Path]:
        report = self.get(report_id)
        if report is None:
            raise NotFoundError("报告不存在")
        file_path = Path(report.file_path)
        if not file_path.exists():
            raise NotFoundError("报告文件不存在")
        return report, file_path
