from __future__ import annotations

from sqlalchemy import Row
from sqlalchemy.orm import Session

from src.core.errors import NotFoundError
from src.data.models.agent_tool_call import AgentToolCall
from src.data.repositories import AgentToolCallRepository
from src.data.services.base_service import BaseService


class AgentToolCallService(BaseService[AgentToolCall, AgentToolCallRepository]):
    """工具调用留痕查询服务。

    注意：列表类查询默认**不取响应体**（单条上限 2MB）。要看响应体请用
    ``get_call`` / ``get_http_request_or_raise`` 单条取，否则详情页会变成几 MB 的 JSON。
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

    # ── 测试报告（按 run 聚合 send_request）──────────────────────────────

    def list_http_run_stats(
        self,
        space_id: int | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Row], int]:
        """报告列表：一行一个 run，只含发过 ``send_request`` 的执行。"""
        return self.repo.list_http_run_stats(space_id, status, page, page_size)

    def list_http_requests(self, run_id: int, include_body: bool = False) -> list[AgentToolCall]:
        """报告详情：某次执行的全部 ``send_request``（默认不含响应体）。"""
        return self.repo.list_http_requests(run_id, include_body=include_body)

    def get_http_request_or_raise(self, run_id: int, request_id: int) -> AgentToolCall:
        """单条请求的完整正文（详情页展开时懒加载）。

        条件同时限 ``run_id`` 与 ``tool_name``：
        用别的 run 的 id 拼 URL 读不到数据，非 HTTP 工具也拿不到。
        """
        call = self.repo.get_http_request(run_id, request_id)
        if call is None:
            raise NotFoundError("请求记录不存在")
        return call
