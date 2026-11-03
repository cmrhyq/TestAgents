"""测试报告接口的数据结构。

报告的语义：**一次执行（run）里所有 ``send_request`` 调用的汇总**。
没有 report 表、也没有报告文件——数据全部来自 ``agent_tool_call``。

⚠️ 成功率的统计口径刻意用 HTTP 2xx，而不是工具层的 ``ok``：

``send_request`` 对 4xx/5xx **不抛异常**（见 ``http_tools._do_request``），
``ok=1`` 只代表「请求发出去了」。拿 ``ok`` 当成功率会把 500 算成成功，
看起来一片绿、实际全是错。为此把两类失败拆开：

- ``error_count``：拿到了响应，但状态码不在 2xx
- ``exception_count``：连状态码都没有（网络异常 / 参数不合法 / 生产环境被拦截）
  ⚠️ 这一类不能用 ``ok=0`` 判断：``send_request`` 返回 ``{"error": ...}`` 时
  工具层仍记为成功，但实际没有任何响应。
"""

from pydantic import BaseModel, Field

from src.data.schemas.agent_run import AgentRunBrief
from src.data.schemas.agent_tool_call import AgentToolCallResponse
from src.data.schemas.common import PaginatedResponse


class ReportStat(BaseModel):
    """一次执行里 HTTP 请求的统计读数。"""

    request_count: int = Field(default=0, description="send_request 调用总数")
    success_count: int = Field(default=0, description="HTTP 2xx 次数")
    error_count: int = Field(default=0, description="拿到响应但非 2xx 的次数")
    exception_count: int = Field(default=0, description="没有状态码的次数（网络异常/参数错误/被拦截）")
    success_rate: float = Field(default=0.0, description="2xx 占比（0-100）")
    avg_duration_ms: float = Field(default=0.0, description="平均耗时（毫秒）")
    first_request_at: str | None = Field(default=None, description="首次请求时间")
    last_request_at: str | None = Field(default=None, description="最后一次请求时间")


class ReportResponse(ReportStat):
    """报告列表项：一个 ``run_id`` 一行。"""

    run_id: int = Field(..., description="执行记录 ID（报告以 run 为单位）")
    title: str = Field(default="", description="执行标题")
    status: str = Field(default="", description="执行状态: running/completed/failed/cancelled")
    mode: str = Field(default="", description="工作模式: agent/ask/plan")
    space_id: int | None = Field(default=None, description="所属空间 ID")
    run_created_at: str = Field(default="", description="执行创建时间")


class ReportListResponse(PaginatedResponse[ReportResponse]):
    """报告列表响应（total 是 run 数，不是请求条数）"""


class ReportDetailResponse(BaseModel):
    """报告详情：执行摘要 + 统计 + 本次执行的全部 HTTP 请求（不含正文）。

    正文走 ``GET /reports/{run_id}/requests/{request_id}`` 懒加载：
    单条响应体上限 2MB，一轮 ReAct 几十次调用，整页拉回来就是几十 MB。
    """

    run: AgentRunBrief
    stat: ReportStat
    requests: list[AgentToolCallResponse] = Field(default_factory=list)
