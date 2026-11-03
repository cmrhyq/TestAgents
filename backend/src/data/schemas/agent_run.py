from pydantic import BaseModel, Field

from src.data.schemas.common import PaginatedResponse


class AgentRunResponse(BaseModel):
    """执行记录响应体。"""

    id: int = Field(..., description="执行记录 ID")
    space_id: int | None = Field(default=None, description="所属空间 ID")
    environment_id: int | None = Field(default=None, description="关联环境 ID")
    conversation_id: int | None = Field(default=None, description="关联会话 ID")
    title: str = Field(default="", description="执行标题，取指令摘要")
    mode: str = Field(default="agent", description="工作模式：agent/ask/plan")
    trigger_type: str = Field(default="chat", description="触发类型：chat/manual/scheduled/ci")
    status: str = Field(..., description="状态：running/completed/failed/cancelled")
    llm_provider: str = Field(default="", description="LLM 提供商")
    llm_model: str = Field(default="", description="LLM 模型名")
    tool_call_count: int = Field(default=0, description="工具调用总数")
    ok_count: int = Field(default=0, description="成功的工具调用数")
    error_count: int = Field(default=0, description="失败的工具调用数")
    success_rate: float = Field(default=0.0, description="工具调用成功率，百分比 0-100")
    avg_response_time: float = Field(default=0.0, description="工具调用平均耗时，毫秒")
    llm_call_count: int = Field(default=0, description="LLM 调用次数")
    total_tokens: int = Field(default=0, description="累计 token 数")
    cost_usd: float = Field(default=0.0, description="预估成本，美元")
    duration_ms: int = Field(default=0, description="总耗时，毫秒")
    started_at: str | None = Field(default=None, description="开始时间")
    finished_at: str | None = Field(default=None, description="结束时间")
    error_message: str = Field(default="", description="错误信息")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class AgentRunBrief(BaseModel):
    """执行记录摘要，嵌入报告详情使用。"""

    id: int
    title: str = ""
    mode: str = "agent"
    status: str = "running"
    llm_provider: str = ""
    llm_model: str = ""
    tool_call_count: int = 0
    ok_count: int = 0
    error_count: int = 0
    success_rate: float = 0.0
    avg_response_time: float = 0.0
    llm_call_count: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    started_at: str | None = None
    finished_at: str | None = None

    model_config = {"from_attributes": True}


class AgentToolCallBrief(BaseModel):
    """工具调用摘要，不含请求与响应正文。"""

    id: int
    seq: int = 0
    tool_name: str = ""
    tool_type: str = "other"
    ok: int = 0
    http_method: str | None = None
    http_url: str | None = None
    http_status_code: int | None = None
    duration_ms: int = 0
    error_type: str = ""
    error_message: str = ""
    created_at: str = ""

    model_config = {"from_attributes": True}


class AgentRunDetail(AgentRunResponse):
    """执行记录详情，附工具调用摘要列表。"""

    tool_calls: list[AgentToolCallBrief] = Field(default_factory=list, description="工具调用摘要，按 seq 升序")


class AgentRunListResponse(PaginatedResponse[AgentRunResponse]):
    """执行记录列表响应。"""


class AgentRunQuery(BaseModel):
    """执行记录查询参数。"""

    space_id: int | None = Field(default=None, description="空间 ID 筛选")
    status: str | None = Field(default=None, description="状态筛选")
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页记录数，1-100")


class AgentCleanupResult(BaseModel):
    """执行记录清理结果。"""

    cutoff: str = Field(..., description="时间截止点，created_at 早于此值的记录被清理")
    days: int = Field(..., description="保留天数")
    space_id: int | None = Field(default=None, description="限定的空间 ID，NULL 表示全部空间")
    dry_run: bool = Field(default=False, description="是否为试运行，true 时不实际删除")
    deleted_runs: int = Field(default=0, description="删除的执行记录数")
    deleted_tool_calls: int = Field(default=0, description="删除的工具调用留痕数")
    deleted_reports: int = Field(default=0, description="删除的报告行数")
    orphan_files: list[str] = Field(default_factory=list, description="已删除记录对应的残留报告文件路径")
