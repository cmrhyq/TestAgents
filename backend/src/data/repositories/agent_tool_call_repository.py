from sqlalchemy import Row, case, delete, func, select
from sqlalchemy.orm import Session, defer

from src.data.constant.tool_names import HTTP_TOOL_NAME
from src.data.models.agent_run import AgentRun
from src.data.models.agent_tool_call import AgentToolCall
from src.data.repositories.base import BaseRepository, RunScopedRepositoryMixin

#: HTTP 2xx —— 报告里的「成功」按它算，而不是工具层的 ``ok``。
#:
#: 原因：``send_request`` 对 4xx/5xx **不抛异常**（``http_tools._do_request``
#: 把状态码塞进返回值），``ToolOutcome.ok`` 只代表「请求发出去了」。
#: 用 ``ok`` 当成功率会把 500 算成成功，口径是错的。
_SUCCESS_CONDITION = AgentToolCall.http_status_code.between(200, 299)


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

    def list_http_requests(self, run_id: int, include_body: bool = False) -> list[AgentToolCall]:
        """某次执行里的全部 ``send_request`` 调用（报告详情用）。

        与 ``list_by_run`` 的区别：只取 HTTP 工具体，靠 ``tool_name`` 过滤。
        """
        stmt = (
            select(AgentToolCall)
            .where(
                AgentToolCall.run_id == run_id,
                AgentToolCall.tool_name == HTTP_TOOL_NAME,
            )
            .order_by(AgentToolCall.seq)
        )
        if not include_body:
            stmt = stmt.options(defer(AgentToolCall.response_body))
        return list(self._session.scalars(stmt).all())

    def get_http_request(self, run_id: int, request_id: int) -> AgentToolCall | None:
        """取单条 ``send_request`` 留痕（含完整请求/响应正文）。

        详情页懒加载用：只有用户展开某一行才走这里，避免整页拉几十 MB。
        同时按 ``run_id`` 限定，防止拿别的执行的 id 越权读取。
        """
        stmt = (
            select(AgentToolCall)
            .where(
                AgentToolCall.id == request_id,
                AgentToolCall.run_id == run_id,
                AgentToolCall.tool_name == HTTP_TOOL_NAME,
            )
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def list_http_run_stats(
        self,
        space_id: int | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Row], int]:
        """按 ``run_id`` 聚合 ``send_request``，返回报告列表的一页。

        **只有真正发过 HTTP 请求的执行才会出现**——没调过 ``send_request``
        的 run 不构成一份「接口测试报告」。

        Returns:
            ``(rows, total)``；``rows`` 每行含 run 的展示字段 + 聚合读数，
            ``total`` 是满足筛选条件的 run 数（不是请求条数）。
        """
        agg = (
            select(
                AgentToolCall.run_id.label("run_id"),
                func.count().label("request_count"),
                func.sum(case((_SUCCESS_CONDITION, 1), else_=0)).label("success_count"),
                # 「异常」= 连状态码都没有（网络异常 / 参数不合法 / 生产环境被拦截）。
                # ⚠️ 不能用 ok==0 判断：``send_request`` 拿到 {"error": ...} 时工具层
                # 仍算成功（ok=1），但根本没有响应，实测库里就有这种行。
                func.sum(
                    case((AgentToolCall.http_status_code.is_(None), 1), else_=0)
                ).label("exception_count"),
                func.avg(AgentToolCall.duration_ms).label("avg_duration_ms"),
                func.min(AgentToolCall.created_at).label("first_request_at"),
                func.max(AgentToolCall.created_at).label("last_request_at"),
            )
            .where(AgentToolCall.tool_name == HTTP_TOOL_NAME)
            .group_by(AgentToolCall.run_id)
            .subquery()
        )

        joins = agg.join(AgentRun, AgentRun.id == agg.c.run_id)

        count_stmt = select(func.count()).select_from(joins)
        stmt = select(
            agg.c.run_id,
            agg.c.request_count,
            agg.c.success_count,
            agg.c.exception_count,
            agg.c.avg_duration_ms,
            agg.c.first_request_at,
            agg.c.last_request_at,
            AgentRun.title,
            AgentRun.status,
            AgentRun.mode,
            AgentRun.space_id,
            AgentRun.created_at.label("run_created_at"),
        ).select_from(joins)

        # 筛选条件建在 agent_run 上，所以统计口径是「执行维度」而不是「请求维度」
        if space_id is not None:
            count_stmt = count_stmt.where(AgentRun.space_id == space_id)
            stmt = stmt.where(AgentRun.space_id == space_id)
        if status:
            count_stmt = count_stmt.where(AgentRun.status == status)
            stmt = stmt.where(AgentRun.status == status)

        total = int(self._session.scalar(count_stmt) or 0)
        rows = list(
            self._session.execute(
                stmt.order_by(agg.c.last_request_at.desc()).limit(page_size).offset((page - 1) * page_size)
            ).all()
        )
        return rows, total

    def get_by_call_id(self, run_id: int, call_id: str) -> AgentToolCall | None:
        stmt = select(AgentToolCall).where(
            AgentToolCall.run_id == run_id, AgentToolCall.call_id == call_id
        ).limit(1)
        return self._session.scalars(stmt).first()

    def delete_by_run_ids(self, run_ids: list[int]) -> int:
        """按执行 ID 批量删除留痕，返回删除行数。"""
        if not run_ids:
            return 0

        result = self._session.execute(delete(AgentToolCall).where(AgentToolCall.run_id.in_(run_ids)))
        return int(result.rowcount or 0)
