from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.models.agent_run import AgentRun
from src.data.models.base import local_now
from src.data.repositories.base import BaseRepository

#: 清理任务只删这几个终态，running 一律不动
TERMINAL_STATUSES = ("completed", "failed", "cancelled")


def cutoff_before(days: int) -> str:
    """返回「days 天前」的时间戳字符串。

    统一走 ``local_now`` 的格式（毫秒精度 ISO 字符串），因为库里存的就是
    这个格式，字符串比较等价于时间比较。手工 ``strftime`` 会丢掉毫秒位，
    导致同一毫秒边界上的记录比较结果不一致。
    """
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


class AgentRunRepository(BaseRepository[AgentRun]):
    """Agent 执行记录数据访问"""

    def __init__(self, session: Session) -> None:
        super().__init__(AgentRun, session)

    def get_by_space(self, space_id: int, limit: int = 50) -> list[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(AgentRun.space_id == space_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_by_ids(self, run_ids: list[int]) -> list[AgentRun]:
        """按 ID 列表批量查询执行记录。"""
        if not run_ids:
            return []
        stmt = select(AgentRun).where(AgentRun.id.in_(run_ids))
        return list(self._session.scalars(stmt).all())

    def get_by_conversation(self, conversation_id: int, limit: int = 100) -> list[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(AgentRun.conversation_id == conversation_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def find_cleanup_candidates(
        self,
        cutoff: str,
        space_id: int | None = None,
        limit: int = 500,
    ) -> list[int]:
        """选出待清理的执行记录 ID（只取终态，且早于 cutoff）。"""
        stmt = select(AgentRun.id).where(
            AgentRun.status.in_(TERMINAL_STATUSES),
            AgentRun.created_at < cutoff,
        )
        if space_id is not None:
            stmt = stmt.where(AgentRun.space_id == space_id)
        return list(self._session.scalars(stmt.order_by(AgentRun.created_at).limit(limit)).all())

    def count_cleanup_candidates(self, cutoff: str, space_id: int | None = None) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(AgentRun).where(
            AgentRun.status.in_(TERMINAL_STATUSES),
            AgentRun.created_at < cutoff,
        )
        if space_id is not None:
            stmt = stmt.where(AgentRun.space_id == space_id)
        return self._session.scalar(stmt) or 0

    def get_stale_running(self, stale_before: str) -> list[AgentRun]:
        """查处于 running 但早已过期的记录（进程被杀留下的「僵尸」）。

        仅用于排障展示，不参与自动清理——终态判断不给 running 开口子。
        """
        stmt = (
            select(AgentRun)
            .where(AgentRun.status == "running", AgentRun.created_at < stale_before)
            .order_by(AgentRun.created_at)
        )
        return list(self._session.scalars(stmt).all())

    def mark_stale_as_failed(self, stale_before: str) -> int:
        """把僵尸 running 记录收尾为 failed，避免永久占用列表。

        Returns:
            实际更新的行数
        """
        rows = self.get_stale_running(stale_before)
        if not rows:
            return 0
        now = local_now()
        for run in rows:
            run.status = "failed"
            run.finished_at = now
            run.error_message = "执行被中断（进程退出或客户端长时间断连），已标记为失败"
            run.updated_at = now
        self._session.flush()
        return len(rows)
