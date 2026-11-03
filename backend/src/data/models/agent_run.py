from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.agent_tool_call import AgentToolCall
    from src.data.models.environment import Environment
    from src.data.models.space import Space


class AgentRun(Base):
    """Agent 执行记录 - 一轮 ReAct 对话对应一条。

    为什么需要这张表：``conversation`` / ``message`` 只回答「说了什么」，
    回答不了「这次回答是怎么得到的、调了几次工具、花了多少 token」。
    ``llm_log`` 有成本但没有轮次边界，``agent_tool_call`` 有细节但没有汇总，
    三者靠 ``run_id`` 串成一条完整链路。

    **统计列是刻意冗余的**：列表页与仪表盘每次翻页都去 ``agent_tool_call``
    做 COUNT/AVG，二十条 run 就是二十次聚合扫描。执行收尾时一次算出即可。
    """

    __tablename__ = "agent_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)

    # ── 归属 ────────────────────────────────────────────────────────────
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    environment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("environment.id", ondelete="SET NULL"))
    # 刻意不建外键：ensure_conversation 在 DB 不可用时返回 0，
    # 建 FK 会让整条执行记录跟着写不进去——记录层不能比业务层更脆弱。
    conversation_id: Mapped[int | None] = mapped_column(Integer, default=None)

    # ── 本轮上下文 ──────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="agent")
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False, default="chat")
    llm_provider: Mapped[str] = mapped_column(Text, nullable=False, default="")
    llm_model: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # ── 生命周期 ────────────────────────────────────────────────────────
    # 刻意没有 pending：记录在「本轮开始」时才插入，插入即 running。
    # 这样终态判定是单条件的 status != 'running'，清理任务不会误删进行中的执行。
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    started_at: Mapped[str | None] = mapped_column(Text, default=None)
    finished_at: Mapped[str | None] = mapped_column(Text, default=None)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── 工具维度统计 ────────────────────────────────────────────────────
    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ok_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 0-100 百分比，与前端进度条口径一致
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── 成本维度（收尾时从 llm_log 聚合）───────────────────────────────
    llm_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    space: Mapped[Space] = relationship(back_populates="agent_runs")
    environment: Mapped[Environment | None] = relationship(back_populates="agent_runs")
    tool_calls: Mapped[list[AgentToolCall]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentToolCall.seq",
    )

    __table_args__ = (
        CheckConstraint("status IN ('running','completed','failed','cancelled')", name="ck_agent_run_status"),
        CheckConstraint("mode IN ('agent','ask','plan')", name="ck_agent_run_mode"),
        CheckConstraint("trigger_type IN ('chat','manual','scheduled','ci')", name="ck_agent_run_trigger"),
        Index("idx_agent_run_space", "space_id", "created_at"),
        Index("idx_agent_run_conv", "conversation_id", "created_at"),
        # 清理任务按 (status, created_at) 过滤，专建复合索引驱动它
        Index("idx_agent_run_status", "status", "created_at"),
        Index("idx_agent_run_created", "created_at"),
    )
