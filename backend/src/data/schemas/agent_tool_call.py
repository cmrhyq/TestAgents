from pydantic import BaseModel, Field

from src.data.schemas.common import PaginatedResponse


class AgentToolCallResponse(BaseModel):
    """工具调用留痕响应体，不含请求与响应正文，供列表使用。"""

    id: int = Field(..., description="留痕 ID")
    run_id: int = Field(..., description="所属执行记录 ID")
    step_index: int = Field(default=0, description="ReAct 轮次，从 0 开始")
    seq: int = Field(default=0, description="本轮内的调用序号")
    call_id: str = Field(default="", description="模型给出的 tool_call_id")
    tool_name: str = Field(default="", description="工具名")
    tool_type: str = Field(default="other", description="工具分类：http/db/fs/exec/memory/knowledge/skill/search/other")
    ok: int = Field(default=0, description="是否成功：1-成功，0-失败")
    error_type: str = Field(default="", description="异常类型")
    error_message: str = Field(default="", description="错误信息")
    result_preview: str = Field(default="", description="结果预览，前 4000 字")
    result_chars: int = Field(default=0, description="结果总字符数，截断前")
    duration_ms: int = Field(default=0, description="耗时，毫秒")
    http_method: str | None = Field(default=None, description="HTTP 方法")
    http_url: str | None = Field(default=None, description="请求 URL")
    http_status_code: int | None = Field(default=None, description="响应状态码")
    response_body_truncated: int = Field(default=0, description="响应体是否被截断：1-是，0-否")
    response_size_bytes: int = Field(default=0, description="响应体原始大小，字节")
    created_at: str = Field(default="", description="创建时间")

    model_config = {"from_attributes": True}


class AgentToolCallDetail(AgentToolCallResponse):
    """工具调用留痕详情，包含完整请求与响应正文。"""

    args_json: str = Field(default="{}", description="工具入参，JSON 对象字符串")
    request_headers: str | None = Field(default=None, description="请求头，敏感值已脱敏")
    request_params: str | None = Field(default=None, description="查询参数")
    request_body: str | None = Field(default=None, description="请求体")
    response_headers: str | None = Field(default=None, description="响应头")
    response_body: str | None = Field(default=None, description="响应体，超过 2MB 时截断")


class AgentToolCallListResponse(PaginatedResponse[AgentToolCallResponse]):
    """工具调用留痕列表响应，默认不含正文。"""


class AgentToolCallDetailListResponse(PaginatedResponse[AgentToolCallDetail]):
    """工具调用留痕列表响应，``include_body=true`` 时使用，含正文。"""
