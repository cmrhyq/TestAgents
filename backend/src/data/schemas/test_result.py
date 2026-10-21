from pydantic import BaseModel, Field

from src.data.schemas.common import PaginatedResponse


class TestResultResponse(BaseModel):
    """TestResult 响应体"""

    id: int = Field(..., description="结果ID")
    run_id: int = Field(..., description="所属执行批次ID")
    test_case_id: int = Field(..., description="关联用例ID")
    case_id: str = Field(..., description="用例标识")
    case_name: str = Field(..., description="用例名称")
    status: str = Field(..., description="状态: pending/running/passed/failed/skipped/error")
    request_url: str = Field(default="", description="请求URL")
    request_method: str = Field(default="", description="请求方法")
    request_headers: str = Field(default="{}", description="请求头 JSON")
    request_body: str | None = Field(default=None, description="请求体")
    query_params: str | None = Field(default=None, description="查询参数")
    response_status_code: int | None = Field(default=None, description="响应状态码")
    response_headers: str = Field(default="{}", description="响应头 JSON")
    response_body: str | None = Field(default=None, description="响应体")
    response_time: float = Field(default=0.0, description="响应耗时 (毫秒)")
    error_message: str = Field(default="", description="错误信息")
    retry_count: int = Field(default=0, description="重试次数")
    started_at: str | None = Field(default=None, description="开始时间")
    finished_at: str | None = Field(default=None, description="结束时间")
    created_at: str = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class TestResultListResponse(PaginatedResponse[TestResultResponse]):
    """TestResult 列表响应"""


class TestResultQuery(BaseModel):
    """TestResult 查询参数"""

    run_id: int | None = Field(default=None, description="执行批次ID筛选")
    test_case_id: int | None = Field(default=None, description="用例ID筛选")
    status: str | None = Field(default=None, description="状态筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
