from __future__ import annotations

from sqlalchemy.orm import Session

from src.data.models.agent_tool_call import AgentToolCall
from src.data.repositories import AgentToolCallRepository
from src.data.services.base_service import BaseService


class AgentToolCallService(BaseService[AgentToolCall, AgentToolCallRepository]):
    """工具调用留痕查询服务。

    列表查询默认不加载响应体（单条上限 2MB）；需要响应体时用 ``get_call`` 单条取。
    """

    def __init__(self, session: Session):
        """绑定会话与留痕仓储。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(session, AgentToolCallRepository(session))

    def list_by_run(self, run_id: int, include_body: bool = False) -> list[AgentToolCall]:
        """按执行记录列出工具调用。

        Args:
            run_id: 执行记录主键
            include_body: 是否加载响应体，默认不加载

        Returns:
            按 ``seq`` 升序的留痕列表
        """
        return self.repo.list_by_run(run_id, include_body=include_body)

    def get_call(self, run_id: int, call_id: str) -> AgentToolCall | None:
        """取单条留痕，含完整响应体。

        Args:
            run_id: 执行记录主键
            call_id: 模型侧的调用标识

        Returns:
            留痕实体；不存在时返回 None
        """
        return self.repo.get_by_call_id(run_id, call_id)

    def count_by_run(self, run_id: int) -> int:
        """统计执行记录下的工具调用数。

        Args:
            run_id: 执行记录主键

        Returns:
            调用条数
        """
        return self.repo.count_by_run(run_id)
