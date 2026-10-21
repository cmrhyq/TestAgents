from pydantic import BaseModel, Field

from src.data.enum.workflow import TestStatus
from src.data.schemas.common import PaginatedResponse


class ReportResponse(BaseModel):
    """Report 响应体"""

    id: int = Field(..., description="报告ID")
    run_id: int = Field(..., description="所属执行批次ID")
    format: str = Field(..., description="报告格式: excel/html/markdown/json")
    file_path: str = Field(..., description="文件路径")
    file_size: int = Field(default=0, description="文件大小 (字节)")
    generated_at: str = Field(..., description="生成时间")
    test_run_name: str = Field(default="", description="所属测试运行名称")

    model_config = {"from_attributes": True}


class ReportListResponse(PaginatedResponse[ReportResponse]):
    """Report 列表响应"""


class TestRunBrief(BaseModel):
    """Report 详情中嵌入的测试运行摘要。"""

    id: int
    name: str = ""
    status: str = TestStatus.PENDING.value
    llm_provider: str = ""
    llm_model: str = ""
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    skipped_cases: int = 0
    error_cases: int = 0
    pass_rate: float = 0.0
    total_duration: float = 0.0
    started_at: str | None = None
    finished_at: str | None = None

    model_config = {"from_attributes": True}


class TestResultDetail(BaseModel):
    """Report 详情中的完整测试结果。"""

    id: int
    case_id: str = ""
    case_name: str = ""
    status: str = ""
    request_url: str = ""
    request_method: str = ""
    request_headers: str = "{}"
    request_body: str | None = None
    query_params: str | None = None
    response_status_code: int | None = None
    response_headers: str = "{}"
    response_body: str | None = None
    response_time: float = 0.0
    error_message: str = ""
    retry_count: int = 0
    started_at: str | None = None
    finished_at: str | None = None

    model_config = {"from_attributes": True}


class ReportDetailResponse(BaseModel):
    """报告详情响应（含测试运行和结果数据）。"""

    id: int
    run_id: int
    format: str = ""
    file_size: int = 0
    generated_at: str = ""
    test_run: TestRunBrief
    test_results: list[TestResultDetail] = Field(default=[])

    model_config = {"from_attributes": True}
