from pydantic import BaseModel, Field


class TestSummaryResponse(BaseModel):
    """TestSummary 响应体"""

    id: int = Field(..., description="摘要ID")
    run_id: int = Field(..., description="所属执行批次ID")
    total: int = Field(default=0, description="总用例数")
    passed: int = Field(default=0, description="通过数")
    failed: int = Field(default=0, description="失败数")
    skipped: int = Field(default=0, description="跳过数")
    error: int = Field(default=0, description="错误数")
    pass_rate: float = Field(default=0.0, description="通过率 (%)")
    avg_response_time: float = Field(default=0.0, description="平均响应时间 (秒)")
    min_response_time: float = Field(default=0.0, description="最小响应时间 (秒)")
    max_response_time: float = Field(default=0.0, description="最大响应时间 (秒)")
    p95_response_time: float = Field(default=0.0, description="P95 响应时间 (秒)")
    total_duration: float = Field(default=0.0, description="总耗时 (秒)")
    failure_reasons: str = Field(default="{}", description="失败原因分布 JSON")
    started_at: str | None = Field(default=None, description="开始时间")
    finished_at: str | None = Field(default=None, description="结束时间")
    created_at: str = Field(..., description="创建时间")

    model_config = {"from_attributes": True}
