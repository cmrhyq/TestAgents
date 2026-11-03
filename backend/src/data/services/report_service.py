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
    """报告记录业务逻辑。

    组合查询会临时构造其他 Service 复用同一会话，不额外开启事务。
    """

    def __init__(self, session: Session):
        """绑定会话与报告仓储。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(session, ReportRepository(session))

    def create_report(self, report: Report) -> Report:
        """写入报告记录并输出日志。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            report: 待持久化的报告实体

        Returns:
            持久化后的报告实体
        """
        logger.info(
            f"创建报告: run_id={report.run_id}, format={report.format}",
            action="create_report",
            run_id=report.run_id,
            format=report.format,
        )
        return self.repo.add(report)

    def get_reports_by_run(self, run_id: int) -> list[Report]:
        """取某次执行的全部报告。

        Args:
            run_id: 执行记录主键

        Returns:
            报告列表；无报告时返回空列表
        """
        return self.repo.get_by_run(run_id)

    def list_reports(self, run_id: int | None, page: int, page_size: int) -> tuple[list[tuple[Report, str]], int]:
        """分页查询报告，附带所属执行记录的标题，按生成时间倒序。

        一次分页加一次批量回查执行记录，避免逐条查询。

        Args:
            run_id: 执行记录主键；None 表示全部
            page: 页码，从 1 开始
            page_size: 每页条数

        Returns:
            ``(report, run_title)`` 列表与总数；执行记录缺失时标题为空串
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
        """取某次执行指定格式的报告。

        Args:
            run_id: 执行记录主键
            report_format: 报告格式标识

        Returns:
            报告实体；不存在时返回 None
        """
        return self.repo.get_by_run_and_format(run_id, report_format)

    def get_detail(self, report_id: int) -> tuple[Report, AgentRun, list[AgentToolCall]]:
        """取报告详情，返回报告、所属执行记录与该次执行的工具调用留痕。

        留痕默认不含响应体，需要时通过单条接口获取。

        Args:
            report_id: 报告主键

        Returns:
            报告、执行记录、工具调用留痕三元组

        Raises:
            NotFoundError: 报告或关联的执行记录不存在
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
        """取报告及其磁盘文件路径，供下载使用。

        只读文件系统元数据，不读取文件内容。

        Args:
            report_id: 报告主键

        Returns:
            报告实体与已确认存在的文件路径

        Raises:
            NotFoundError: 报告记录或磁盘文件不存在
        """
        report = self.get(report_id)
        if report is None:
            raise NotFoundError("报告不存在")
        file_path = Path(report.file_path)
        if not file_path.exists():
            raise NotFoundError("报告文件不存在")
        return report, file_path
