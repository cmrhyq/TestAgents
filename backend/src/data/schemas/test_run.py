from pydantic import BaseModel, Field

from src.data.schemas.common import PaginatedResponse


class TestRunResponse(BaseModel):
    """TestRun 响应体"""

    id: int = Field(..., description="执行批次ID")
    space_id: int | None = Field(default=None, description="所属空间ID")
    environment_id: int | None = Field(default=None, description="关联环境ID")
    name: str = Field(default="", description="批次名称")
    status: str = Field(..., description="状态: pending/running/completed/failed/cancelled")
    trigger_type: str = Field(default="manual", description="触发类型: manual/scheduled/ci")
    llm_provider: str = Field(default="", description="LLM 提供商")
    llm_model: str = Field(default="", description="LLM 模型名称")
    total_cases: int = Field(default=0, description="总用例数")
    passed_cases: int = Field(default=0, description="通过数")
    failed_cases: int = Field(default=0, description="失败数")
    skipped_cases: int = Field(default=0, description="跳过数")
    error_cases: int = Field(default=0, description="错误数")
    pass_rate: float = Field(default=0.0, description="通过率 (%)")
    total_duration: float = Field(default=0.0, description="总耗时 (秒)")
    started_at: str | None = Field(default=None, description="开始时间")
    finished_at: str | None = Field(default=None, description="结束时间")
    error_message: str = Field(default="", description="错误信息")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class TestCaseBrief(BaseModel):
    """TestRun 详情中的用例摘要。"""

    id: int
    case_name: str = ""
    method: str = ""
    url: str = ""
    priority: str = ""
    status: int | str = ""
    created_at: str = ""

    model_config = {"from_attributes": True}


class TestResultBrief(BaseModel):
    """TestRun 详情中的结果摘要。"""

    id: int
    test_case_id: int | None = None
    status: str = ""
    status_code: int | None = None
    response_time: float = 0.0
    assertion_passed: int = 0
    assertion_failed: int = 0
    error_message: str = ""
    created_at: str = ""

    model_config = {"from_attributes": True}


class TestRunDetail(TestRunResponse):
    """TestRun 详情响应（含用例与结果列表）。"""

    test_cases: list[TestCaseBrief] = Field(default=[])
    test_results: list[TestResultBrief] = Field(default=[])


class TestRunListResponse(PaginatedResponse[TestRunResponse]):
    """TestRun 列表响应"""


class TestRunQuery(BaseModel):
    """TestRun 查询参数"""

    space_id: int | None = Field(default=None, description="空间ID筛选")
    status: str | None = Field(default=None, description="状态筛选")
    trigger_type: str | None = Field(default=None, description="触发类型筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
