from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.agent_run import AgentRun


class AgentToolCall(Base):
    """单次工具调用的留痕：入参、结果与 HTTP 请求/响应。

    通用列必填、HTTP 列可空，同一张表容纳 ``send_request`` 与非 HTTP 工具。
    正文长度台阶：落库上限 2MB（超限置 ``response_body_truncated=1``），
    给模型 8000 字符，SSE 下发 4000 字符。
    """

    __tablename__ = "agent_tool_call"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    # 所属执行记录，agent_run.id；执行记录删除时级联删除
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("agent_run.id", ondelete="CASCADE"), nullable=False)

    # ── 通用列（所有工具都填）───────────────────────────────────────────
    # ReAct 轮次序号，从 0 开始
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 本轮内的调用序号，同一次执行内递增
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 模型给出的 tool_call_id，用于把结果回填到对应调用
    call_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 工具分类，取值见 __table_args__ 中的检查约束
    tool_type: Mapped[str] = mapped_column(Text, nullable=False, default="other")
    # 工具入参，JSON 对象字符串
    args_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # 1-成功，0-失败
    ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 异常类型：异常被 runner 捕获后由本列显式带出，用于统计失败原因
    error_type: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 结果前 4000 字，与 SSE 下发口径一致
    result_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 结果总字符数（截断前）
    result_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 调用耗时，毫秒
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    # ── HTTP 列（仅 send_request 填，其余工具为 NULL）───────────────────
    http_method: Mapped[str | None] = mapped_column(Text, default=None)
    http_url: Mapped[str | None] = mapped_column(Text, default=None)
    http_status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    # 请求头，JSON 对象字符串，敏感值已脱敏
    request_headers: Mapped[str | None] = mapped_column(Text, default=None)
    # 查询参数，JSON 对象字符串
    request_params: Mapped[str | None] = mapped_column(Text, default=None)
    request_body: Mapped[str | None] = mapped_column(Text, default=None)
    response_headers: Mapped[str | None] = mapped_column(Text, default=None)
    response_body: Mapped[str | None] = mapped_column(Text, default=None)
    # 1-响应体超过 2MB 已截断，0-完整
    response_body_truncated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 响应体原始大小，字节
    response_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    run: Mapped[AgentRun] = relationship(back_populates="tool_calls")

    __table_args__ = (
        CheckConstraint(
            "tool_type IN ('http','db','fs','exec','memory','knowledge','skill','search','other')",
            name="ck_tool_call_type",
        ),
        CheckConstraint("ok IN (0,1)", name="ck_tool_call_ok"),
        Index("idx_atc_run", "run_id", "seq"),
        Index("idx_atc_tool_created", "tool_name", "created_at"),
        # 测试报告按 tool_name 过滤 + 按 run_id 分组，这条索引专供它
        Index("idx_atc_tool_run", "tool_name", "run_id"),
        Index("idx_atc_http_url", "http_url"),
    )
