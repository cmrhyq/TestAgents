from pydantic import BaseModel, Field

from src.data.schemas.common import PaginatedResponse


class TestCaseResponse(BaseModel):
    """TestCase 响应体"""

    id: int = Field(..., description="用例ID")
    run_id: int = Field(..., description="所属执行批次ID")
    endpoint_id: int | None = Field(default=None, description="关联接口ID")
    case_id: str = Field(..., description="用例标识")
    case_name: str = Field(..., description="用例名称")
    url: str = Field(..., description="请求URL")
    method: str = Field(..., description="HTTP方法")
    scenario_type: str = Field(default="normal", description="场景类型")
    priority: str = Field(default="P1", description="优先级: P0/P1/P2")
    headers: str = Field(default="{}", description="请求头 JSON")
    body: str | None = Field(default=None, description="请求体 JSON")
    params: str | None = Field(default=None, description="查询参数 JSON")
    cache_rules: str | None = Field(default=None, description="缓存规则 JSON")
    assert_rules: str = Field(default="[]", description="断言规则 JSON")
    expected_result: str = Field(default="成功", description="预期结果")
    description: str = Field(default="", description="描述")
    generated_by: str = Field(default="llm", description="生成方式: llm/manual/import")
    status: int = Field(default=1, description="状态: 1=启用")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class TestCaseDetail(TestCaseResponse):
    """TestCase 详情响应（含执行结果数量）"""

    result_count: int | None = Field(default=0, description="执行结果数量")

    model_config = {"from_attributes": True}


class TestCaseListResponse(PaginatedResponse[TestCaseResponse]):
    """TestCase 列表响应"""


class TestCaseQuery(BaseModel):
    """TestCase 查询参数"""

    run_id: int | None = Field(default=None, description="执行批次ID筛选")
    endpoint_id: int | None = Field(default=None, description="接口ID筛选")
    scenario_type: str | None = Field(default=None, description="场景类型筛选")
    priority: str | None = Field(default=None, description="优先级筛选")
    status: int | None = Field(default=None, description="状态筛选")
    keyword: str | None = Field(default=None, description="关键字搜索")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
