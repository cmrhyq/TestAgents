from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.models.agent_run import AgentRun
from src.data.models.base import local_now
from src.data.repositories.base import BaseRepository

#: 可清理的终态；不含 running，避免清理进行中的执行记录
TERMINAL_STATUSES = ("completed", "failed", "cancelled")


def cutoff_before(days: int) -> str:
    """返回 ``days`` 天前的时间戳字符串。

    格式须与 ``local_now`` 一致（毫秒精度 ISO 字符串），库中存储的也是该格式，
    字符串比较才等价于时间比较；手写 ``strftime`` 丢毫秒会破坏边界比较。

    Args:
        days: 回溯天数，正数表示过去

    Returns:
        形如 ``2024-01-01T00:00:00.000`` 的时间字符串
    """
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


class AgentRunRepository(BaseRepository[AgentRun]):
    """执行记录表数据访问。"""

    def __init__(self, session: Session) -> None:
        """绑定执行记录模型。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(AgentRun, session)

    def get_by_space(self, space_id: int, limit: int = 50) -> list[AgentRun]:
        """按空间取最近的执行记录。

        Args:
            space_id: 空间主键
            limit: 最多返回条数

        Returns:
            按创建时间倒序的执行记录列表
        """
        stmt = (
            select(AgentRun)
            .where(AgentRun.space_id == space_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_by_ids(self, run_ids: list[int]) -> list[AgentRun]:
        """按主键列表批量查询执行记录。

        Args:
            run_ids: 执行记录主键列表

        Returns:
            匹配的记录；入参为空时返回空列表
        """
        if not run_ids:
            return []
        stmt = select(AgentRun).where(AgentRun.id.in_(run_ids))
        return list(self._session.scalars(stmt).all())

    def get_by_conversation(self, conversation_id: int, limit: int = 100) -> list[AgentRun]:
        """按会话取执行记录。

        Args:
            conversation_id: 会话主键
            limit: 最多返回条数

        Returns:
            按创建时间倒序的执行记录列表
        """
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
        """选出待清理的执行记录主键。

        只取终态且创建时间早于 ``cutoff`` 的记录，``running`` 不会被选中。

        Args:
            cutoff: 时间上界字符串，格式同 ``cutoff_before`` 的返回值
            space_id: 限定空间；None 表示全部空间
            limit: 最多返回条数

        Returns:
            按创建时间升序排列的主键列表
        """
        stmt = select(AgentRun.id).where(
            AgentRun.status.in_(TERMINAL_STATUSES),
            AgentRun.created_at < cutoff,
        )
        if space_id is not None:
            stmt = stmt.where(AgentRun.space_id == space_id)
        return list(self._session.scalars(stmt.order_by(AgentRun.created_at).limit(limit)).all())

    def count_cleanup_candidates(self, cutoff: str, space_id: int | None = None) -> int:
        """统计待清理的执行记录数，口径与 ``find_cleanup_candidates`` 一致。

        Args:
            cutoff: 时间上界字符串
            space_id: 限定空间；None 表示全部空间

        Returns:
            满足条件的记录数
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(AgentRun).where(
            AgentRun.status.in_(TERMINAL_STATUSES),
            AgentRun.created_at < cutoff,
        )
        if space_id is not None:
            stmt = stmt.where(AgentRun.space_id == space_id)
        return self._session.scalar(stmt) or 0

    def get_stale_running(self, stale_before: str) -> list[AgentRun]:
        """查询早已过期的 ``running`` 记录，即进程被杀后残留的数据。

        仅供排障展示，不参与自动清理：清理只处理终态。

        Args:
            stale_before: 时间上界字符串，早于该值的记录视为过期

        Returns:
            按创建时间升序的 ``running`` 记录列表
        """
        stmt = (
            select(AgentRun)
            .where(AgentRun.status == "running", AgentRun.created_at < stale_before)
            .order_by(AgentRun.created_at)
        )
        return list(self._session.scalars(stmt).all())

    def mark_stale_as_failed(self, stale_before: str) -> int:
        """把过期的 ``running`` 记录置为 ``failed`` 并补写结束时间。

        副作用：写库（未提交），需调用方提交事务；同时写入失败原因文本。

        Args:
            stale_before: 时间上界字符串，早于该值的记录视为过期

        Returns:
            实际更新的行数；无过期记录时返回 0
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
