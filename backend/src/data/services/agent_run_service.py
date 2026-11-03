from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.data.models.agent_run import AgentRun
from src.data.repositories import AgentRunRepository, AgentToolCallRepository
from src.data.repositories.agent_run_repository import cutoff_before
from src.data.services.base_service import BaseService

logger = get_logger(__name__)

#: 清理时每批处理多少条执行记录
DEFAULT_BATCH_SIZE = 500


class AgentRunService(BaseService[AgentRun, AgentRunRepository]):
    def __init__(self, session: Session):
        super().__init__(session, AgentRunRepository(session))

    def get_run(self, run_id: int) -> AgentRun | None:
        return self.repo.get_by_id(run_id)

    def list_runs(
        self,
        space_id: int | None,
        status: str | None,
        page: int,
        page_size: int,
    ):
        filters = []
        if space_id is not None:
            filters.append(AgentRun.space_id == space_id)
        if status is not None:
            filters.append(AgentRun.status == status)
        # 老的 list_runs 没排序，列表页顺序随 SQLite 心情；这里显式按创建时间倒序
        return self.list(page, page_size, *filters, order_by=[AgentRun.created_at.desc()])

    def get_runs_by_ids(self, run_ids: list[int]) -> list[AgentRun]:
        """按 ID 列表批量获取（避免逐条查询）。"""
        return self.repo.get_by_ids(run_ids)

    def cleanup_runs(
        self,
        days: int = 90,
        space_id: int | None = None,
        dry_run: bool = False,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> dict:
        """删除 N 天前的**终态**执行记录及其工具留痕。

        几条硬规则（每条都对应一个真实故障场景）：

        1. **只删终态**：``running`` 一律不动——它可能是异常中断的活会话，
           删掉会让正在跑的用户看到「记录消失」。
        2. **时间口径用 created_at**：``started_at`` 可空，不可靠。
        3. **分批提交**：一次大事务会长时间占住 WAL 写锁，把正在进行的对话
           全部卡死。

        报告不再是独立表：它按 ``run_id`` 聚合 ``agent_tool_call``，
        删掉 run 与留痕，报告自然消失，无需额外清理。

        Args:
            days: 保留最近多少天
            space_id: 只清理指定空间；None 表示全部
            dry_run: 只统计不删除
            batch_size: 每批处理条数

        Returns:
            清理结果字典，可直接喂给 ``AgentCleanupResult``
        """
        days = max(int(days), 1)
        cutoff = cutoff_before(days)
        result = {
            "cutoff": cutoff,
            "days": days,
            "space_id": space_id,
            "dry_run": dry_run,
            "deleted_runs": 0,
            "deleted_tool_calls": 0,
        }

        if dry_run:
            result["deleted_runs"] = self.repo.count_cleanup_candidates(cutoff, space_id)
            return result

        tool_repo = AgentToolCallRepository(self._session)

        while True:
            run_ids = self.repo.find_cleanup_candidates(cutoff, space_id, batch_size)
            if not run_ids:
                break

            result["deleted_tool_calls"] += tool_repo.delete_by_run_ids(run_ids)

            for run_id in run_ids:
                self.repo.delete_by_id(run_id)
            result["deleted_runs"] += len(run_ids)

        # get_db 负责最终 commit；这里显式 flush 让计数与后续查询一致
        self._session.flush()
        logger.info(
            "执行记录清理完成",
            action="cleanup_agent_runs",
            days=days,
            space_id=space_id,
            deleted_runs=result["deleted_runs"],
            deleted_tool_calls=result["deleted_tool_calls"],
        )
        return result

    def mark_stale_running(self, stale_minutes: int = 60) -> int:
        """把超过 N 分钟仍是 running 的记录标记为 failed。

        进程被 kill 时 finally 来不及执行，记录会永久停在 running。
        """
        from datetime import datetime, timedelta

        stale_before = (datetime.now() - timedelta(minutes=stale_minutes)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        count = self.repo.mark_stale_as_failed(stale_before)
        if count:
            logger.info("已将僵死执行记录标记为失败", count=count, stale_minutes=stale_minutes)
        return count
