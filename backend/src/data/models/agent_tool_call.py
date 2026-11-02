from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.agent_run import AgentRun


class AgentToolCall(Base):
    """单次工具调用的完整留痕：入参、结果、HTTP 请求/响应。

    设计要点：**通用列必填，HTTP 列全部可空**。这样一张表同时容纳
    ``send_request`` 与 ``query_db`` / ``read_file`` 这类非 HTTP 工具。

    为什么不用「一个 JSON 万能列」：``v_http_endpoint_stats`` 需要
    ``GROUP BY http_url, http_method``，JSON 列在 SQLite 里无法走索引，
    而且详情页还要按 ``http_status_code`` 过滤。

    长度台阶（三级，互不污染）::

        落库 2MB（本表，超限置 response_body_truncated=1）
            ↑
        给模型 8000 字符（runner._for_model）
            ↑
        SSE 下发 4000 字符（events._truncate）
    """

    __tablename__ = "agent_tool_call"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("agent_run.id", ondelete="CASCADE"), nullable=False)

    # ── 通用列（所有工具都填）───────────────────────────────────────────
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    call_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_type: Mapped[str] = mapped_column(Text, nullable=False, default="other")
    args_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 工具异常被 runner 吞掉了，异常类型与原文必须显式带出，否则查不到「为什么老失败」
    error_type: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 前 4000 字，与 SSE 下发口径对齐，便于「库里看到的 = 前端看到的」
    result_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    # ── HTTP 列（仅 send_request 填，其余工具为 NULL）───────────────────
    http_method: Mapped[str | None] = mapped_column(Text, default=None)
    http_url: Mapped[str | None] = mapped_column(Text, default=None)
    http_status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    request_headers: Mapped[str | None] = mapped_column(Text, default=None)
    request_params: Mapped[str | None] = mapped_column(Text, default=None)
    request_body: Mapped[str | None] = mapped_column(Text, default=None)
    response_headers: Mapped[str | None] = mapped_column(Text, default=None)
    response_body: Mapped[str | None] = mapped_column(Text, default=None)
    response_body_truncated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
        Index("idx_atc_http_url", "http_url"),
    )
