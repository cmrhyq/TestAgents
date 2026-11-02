from __future__ import annotations

from sqlalchemy.orm import Session

from src.data.models.agent_tool_call import AgentToolCall
from src.data.repositories import AgentToolCallRepository
from src.data.services.base_service import BaseService


class AgentToolCallService(BaseService[AgentToolCall, AgentToolCallRepository]):
    """工具调用留痕查询服务。

    注意：列表类查询默认**不取响应体**（单条上限 2MB）。要看响应体请用
    ``get_call`` 单条取，否则详情页会变成几 MB 的 JSON。
    """

    def __init__(self, session: Session):
        super().__init__(session, AgentToolCallRepository(session))

    def list_by_run(self, run_id: int, include_body: bool = False) -> list[AgentToolCall]:
        return self.repo.list_by_run(run_id, include_body=include_body)

    def get_call(self, run_id: int, call_id: str) -> AgentToolCall | None:
        """取单条（含完整响应体）。"""
        return self.repo.get_by_call_id(run_id, call_id)

    def count_by_run(self, run_id: int) -> int:
        return self.repo.count_by_run(run_id)
