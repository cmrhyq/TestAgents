from pydantic import BaseModel, Field

from src.data.schemas.agent_run import AgentRunBrief
from src.data.schemas.agent_tool_call import AgentToolCallDetail
from src.data.schemas.common import PaginatedResponse


class ReportResponse(BaseModel):
    """Report 响应体"""

    id: int = Field(..., description="报告 ID")
    run_id: int = Field(..., description="所属执行记录 ID")
    format: str = Field(..., description="报告格式: excel/html/markdown/json")
    file_path: str = Field(..., description="文件路径")
    file_size: int = Field(default=0, description="文件大小 (字节)")
    generated_at: str = Field(..., description="生成时间")
    run_title: str = Field(default="", description="所属执行记录标题")

    model_config = {"from_attributes": True}


class ReportListResponse(PaginatedResponse[ReportResponse]):
    """Report 列表响应"""


class ReportDetailResponse(BaseModel):
    """报告详情响应（含执行记录统计与工具调用留痕）。"""

    id: int
    run_id: int
    format: str = ""
    file_size: int = 0
    generated_at: str = ""
    run: AgentRunBrief
    tool_calls: list[AgentToolCallDetail] = Field(default_factory=list)

    model_config = {"from_attributes": True}
