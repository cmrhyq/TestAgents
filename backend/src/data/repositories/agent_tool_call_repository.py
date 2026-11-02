from sqlalchemy import select
from sqlalchemy.orm import Session, defer

from src.data.models.agent_tool_call import AgentToolCall
from src.data.repositories.base import BaseRepository, RunScopedRepositoryMixin


class AgentToolCallRepository(RunScopedRepositoryMixin[AgentToolCall], BaseRepository[AgentToolCall]):
    """Agent 工具调用留痕数据访问"""

    def __init__(self, session: Session) -> None:
        super().__init__(AgentToolCall, session)

    def list_by_run(self, run_id: int, include_body: bool = False) -> list[AgentToolCall]:
        """按执行记录查询工具调用。

        Args:
            run_id: 执行记录 ID
            include_body: 是否包含响应体。默认 **不取**——单条响应体上限 2MB，
                详情页一次拉回几十条会把内存和带宽都打爆。
        """
        stmt = select(AgentToolCall).where(AgentToolCall.run_id == run_id).order_by(AgentToolCall.seq)
        if not include_body:
            stmt = stmt.options(defer(AgentToolCall.response_body))
        return list(self._session.scalars(stmt).all())

    def get_by_call_id(self, run_id: int, call_id: str) -> AgentToolCall | None:
        stmt = select(AgentToolCall).where(
            AgentToolCall.run_id == run_id, AgentToolCall.call_id == call_id
        ).limit(1)
        return self._session.scalars(stmt).first()

    def delete_by_run_ids(self, run_ids: list[int]) -> int:
        """按执行 ID 批量删除留痕，返回删除行数。"""
        if not run_ids:
            return 0
        from sqlalchemy import delete

        result = self._session.execute(delete(AgentToolCall).where(AgentToolCall.run_id.in_(run_ids)))
        return int(result.rowcount or 0)
