from datetime import datetime

from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.data.enum.workflow import TestStatus
from src.data.models.base import local_now
from src.data.models.test_run import TestRun
from src.data.repositories import TestRunRepository
from src.data.services.base_service import BaseService

logger = get_logger(__name__)


class TestRunService(BaseService[TestRun, TestRunRepository]):
    def __init__(self, session: Session):
        super().__init__(session, TestRunRepository(session))

    def create_run(self, test_run: TestRun) -> TestRun:
        """创建执行批次"""
        logger.info(f"创建执行批次: {test_run.name}", action="create_run", name=test_run.name)
        return self.repo.add(test_run)

    def get_run(self, run_id: int) -> TestRun | None:
        """获取执行批次"""
        return self.repo.get_by_id(run_id)

    def update_status(self, run_id: int, status: str, error_message: str = "") -> None:
        """更新执行状态"""
        logger.info(
            f"更新批次状态: run_id={run_id}, status={status}", action="update_status", run_id=run_id, status=status
        )
        fields = {"status": status}
        if status == "running":
            fields["started_at"] = local_now()
        elif status in {"completed", "failed", "cancelled"}:
            fields["finished_at"] = local_now()
        if error_message:
            fields["error_message"] = error_message
        self.update(run_id, **fields)

    def update_statistics(
        self,
        run_id: int,
        total: int,
        passed: int,
        failed: int,
        skipped: int,
        error: int,
        pass_rate: float,
        total_duration: float,
    ) -> None:
        """更新统计数据"""
        logger.info(
            f"更新批次统计: run_id={run_id}, total={total}, pass_rate={pass_rate:.2f}%",
            action="update_statistics",
            run_id=run_id,
            total=total,
            pass_rate=pass_rate,
        )
        self.update(
            run_id,
            total_cases=total,
            passed_cases=passed,
            failed_cases=failed,
            skipped_cases=skipped,
            error_cases=error,
            pass_rate=pass_rate,
            total_duration=total_duration,
        )

    def finalize_run(
        self,
        run_id: int,
        total: int,
        passed: int,
        failed: int,
        skipped: int,
        error: int,
        pass_rate: float,
    ) -> None:
        """执行收尾：置为 completed、写入 finished_at、计算耗时并落统计。

        single / flow 执行节点共用，避免重复的状态机与时间戳逻辑。
        """
        self.update_status(run_id, TestStatus.COMPLETED.value)
        run = self.get_run(run_id)
        duration = 0.0
        if run is not None and run.started_at and run.finished_at:
            try:
                start = datetime.fromisoformat(run.started_at)
                end = datetime.fromisoformat(run.finished_at)
                duration = (end - start).total_seconds()
            except ValueError:
                duration = 0.0
        self.update_statistics(
            run_id,
            total,
            passed,
            failed,
            skipped,
            error,
            round(pass_rate, 2),
            round(duration, 2),
        )

    def get_runs_by_space(self, space_id: int, limit: int = 50) -> list[TestRun]:
        """按空间获取执行批次列表"""
        return self.repo.get_by_space(space_id, limit)

    def get_runs_by_ids(self, run_ids: list[int]) -> list[TestRun]:
        """按 ID 列表批量获取执行批次（避免逐条查询）。"""
        return self.repo.get_by_ids(run_ids)

    def list_runs(self, space_id: int | None, status: str | None, page: int, page_size: int):
        filters = []
        if space_id is not None:
            filters.append(TestRun.space_id == space_id)
        if status is not None:
            filters.append(TestRun.status == status)
        return self.list(page, page_size, *filters)
