from sqlalchemy import select
from sqlalchemy.orm import Session, defer

from src.data.models.agent_tool_call import AgentToolCall
from src.data.repositories.base import BaseRepository, RunScopedRepositoryMixin


class AgentToolCallRepository(RunScopedRepositoryMixin[AgentToolCall], BaseRepository[AgentToolCall]):
    """工具调用留痕表数据访问。

    留痕按执行记录（``run_id``）归属，随执行记录一并清理。
    """

    def __init__(self, session: Session) -> None:
        """绑定留痕模型。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(AgentToolCall, session)

    def list_by_run(self, run_id: int, include_body: bool = False) -> list[AgentToolCall]:
        """按执行记录查询工具调用，按 ``seq`` 升序。

        单条响应体上限 2MB，默认延迟加载该列，避免详情页一次拉回大量数据。

        Args:
            run_id: 执行记录主键
            include_body: 是否加载 ``response_body``，默认不加载

        Returns:
            工具调用列表，未加载的响应体在访问时触发额外查询
        """
        stmt = select(AgentToolCall).where(AgentToolCall.run_id == run_id).order_by(AgentToolCall.seq)
        if not include_body:
            stmt = stmt.options(defer(AgentToolCall.response_body))
        return list(self._session.scalars(stmt).all())

    def get_by_call_id(self, run_id: int, call_id: str) -> AgentToolCall | None:
        """按执行记录与调用标识取单条留痕。

        Args:
            run_id: 执行记录主键
            call_id: 模型侧的调用标识

        Returns:
            留痕实体；不存在时返回 None
        """
        stmt = select(AgentToolCall).where(
            AgentToolCall.run_id == run_id, AgentToolCall.call_id == call_id
        ).limit(1)
        return self._session.scalars(stmt).first()

    def delete_by_run_ids(self, run_ids: list[int]) -> int:
        """按执行记录批量删除留痕，走批量 DELETE 而非逐条删除。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            run_ids: 执行记录主键列表

        Returns:
            删除行数；入参为空时返回 0
        """
        if not run_ids:
            return 0
        from sqlalchemy import delete

        result = self._session.execute(delete(AgentToolCall).where(AgentToolCall.run_id.in_(run_ids)))
        return int(result.rowcount or 0)
