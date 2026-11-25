from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.data.constant.agent import DEFAULT_BATCH_SIZE
from src.data.models.agent_run import AgentRun
from src.data.repositories import AgentRunRepository, AgentToolCallRepository
from src.data.repositories.agent_run_repository import cutoff_before
from src.data.services.base_service import BaseService

logger = get_logger(__name__)


class AgentRunService(BaseService[AgentRun, AgentRunRepository]):
    """执行记录业务逻辑，含过期清理与僵死记录收尾。"""

    def __init__(self, session: Session):
        """绑定会话与执行记录仓储。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(session, AgentRunRepository(session))

    def get_run(self, run_id: int) -> AgentRun | None:
        """按主键取执行记录。

        Args:
            run_id: 执行记录主键

        Returns:
            执行记录；不存在时返回 None
        """
        return self.repo.get_by_id(run_id)

    def list_runs(
        self,
        space_id: int | None,
        status: str | None,
        page: int,
        page_size: int,
    ):
        """按空间与状态分页查询执行记录，按创建时间倒序。

        Args:
            space_id: 空间主键；None 表示全部空间
            status: 状态过滤；None 表示不过滤
            page: 页码，从 1 开始
            page_size: 每页条数

        Returns:
            当前页执行记录列表与总数
        """
        filters = []
        if space_id is not None:
            filters.append(AgentRun.space_id == space_id)
        if status is not None:
            filters.append(AgentRun.status == status)
        # 不依赖数据库默认顺序，显式按创建时间倒序
        return self.list(page, page_size, *filters, order_by=[AgentRun.created_at.desc()])

    def get_runs_by_ids(self, run_ids: list[int]) -> list[AgentRun]:
        """按主键列表批量取执行记录，避免逐条查询。

        Args:
            run_ids: 执行记录主键列表

        Returns:
            匹配的记录；入参为空时返回空列表
        """
        return self.repo.get_by_ids(run_ids)

    def cleanup_runs(
        self,
        days: int = 90,
        space_id: int | None = None,
        dry_run: bool = False,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> dict:
        """删除 ``days`` 天前的终态执行记录及其工具留痕与报告行。

        约束：只删终态，``running`` 一律不动；时间口径用 ``created_at``，
        因为 ``started_at`` 可空；报告文件不删除，只在结果中返回路径。

        副作用：写库（未提交），最终提交由 ``get_db`` 负责；不触碰磁盘文件。

        Args:
            days: 保留最近天数，小于 1 时按 1 处理
            space_id: 只清理指定空间；None 表示全部空间
            dry_run: 只统计不删除，此时不产生写操作
            batch_size: 每批处理的记录条数，用于避免长事务占用写锁

        Returns:
            清理结果字典，字段与 ``AgentCleanupResult`` 对应；``orphan_files``
            为已删除报告行对应的磁盘路径
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

        # 最终提交由 get_db 负责；此处 flush 保证计数与后续查询一致
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
        """把超过指定时长仍为 ``running`` 的记录标记为 ``failed``。

        进程被强制终止时 ``finally`` 不会执行，记录会一直停在 ``running``。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            stale_minutes: 判定过期的分钟数

        Returns:
            实际更新的记录数
        """
        from datetime import datetime, timedelta

        stale_before = (datetime.now() - timedelta(minutes=stale_minutes)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        count = self.repo.mark_stale_as_failed(stale_before)
        if count:
            logger.info("已将僵死执行记录标记为失败", count=count, stale_minutes=stale_minutes)
        return count
