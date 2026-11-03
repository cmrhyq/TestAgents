from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.agent_tool_call import AgentToolCall
    from src.data.models.environment import Environment
    from src.data.models.report import Report
    from src.data.models.space import Space


class AgentRun(Base):
    """Agent 执行记录 - 一轮 ReAct 对话对应一条。

    ``conversation`` / ``message`` 记录对话内容，本表记录这一轮怎么得出结果；
    与 ``agent_tool_call``、``llm_log`` 通过 ``run_id`` 关联。
    统计列在收尾时一次算出并冗余落库，列表页不再聚合明细表。
    """

    __tablename__ = "agent_run"

    # 主键，由 next_id() 生成，不走数据库自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)

    # ── 归属 ────────────────────────────────────────────────────────────
    # 所属空间，space.id；空间删除时级联删除
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    # 执行所用环境，environment.id；环境删除时置空
    environment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("environment.id", ondelete="SET NULL"))
    # 关联会话，conversation.id；不建外键：会话创建失败时执行记录仍需写入
    conversation_id: Mapped[int | None] = mapped_column(Integer, default=None)

    # ── 本轮上下文 ──────────────────────────────────────────────────────
    # 执行标题，取指令摘要
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 工作模式，取值 agent / ask / plan
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="agent")
    # 触发来源，取值 chat / manual / scheduled / ci
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False, default="chat")
    # LLM 提供商名
    llm_provider: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # LLM 模型名
    llm_model: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # ── 生命周期 ────────────────────────────────────────────────────────
    # 取值 running / completed / failed / cancelled；无 pending 态，插入即 running
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    started_at: Mapped[str | None] = mapped_column(Text, default=None)
    finished_at: Mapped[str | None] = mapped_column(Text, default=None)
    # 总耗时，毫秒
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── 工具维度统计 ────────────────────────────────────────────────────
    # 工具调用总次数
    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 成功的工具调用次数
    ok_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 失败的工具调用次数
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 工具调用成功率，百分比 0-100
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 工具调用平均耗时，毫秒
    avg_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── 成本维度（收尾时从 llm_log 聚合）───────────────────────────────
    # LLM 调用次数
    llm_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 输入与输出 token 之和
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 预估成本，美元
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
    reports: Mapped[list[Report]] = relationship(back_populates="run", cascade="all, delete-orphan")

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
