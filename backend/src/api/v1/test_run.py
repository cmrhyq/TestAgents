"""测试运行查询路由。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.data.schemas.test_run import (
    TestCaseBrief,
    TestResultBrief,
    TestRunDetail,
    TestRunListResponse,
    TestRunResponse,
)
from src.data.services import TestCaseService, TestResultService, TestRunService

router = APIRouter(prefix="/test/runs", tags=["测试运行"])


@router.get("/", response_model=TestRunListResponse)
def list_test_runs(
    space_id: int | None = Query(default=None, description="空间ID筛选"),
    status: str | None = Query(default=None, description="状态筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """查询测试运行列表（分页）。"""
    items, total = TestRunService(db).list_runs(space_id, status, page, page_size)
    return TestRunListResponse(
        items=[TestRunResponse.model_validate(r) for r in items], total=total, page=page, page_size=page_size
    )


@router.get("/{run_id}", response_model=TestRunDetail)
def get_test_run(run_id: int, db: Session = Depends(get_db)):
    """获取测试运行详情（含用例和结果）。"""
    service = TestRunService(db)
    run = service.get_or_raise(run_id, "测试运行不存在")

    cases = TestCaseService(db).get_cases_by_run(run_id)
    results = TestResultService(db).get_results_by_run(run_id)

    return TestRunDetail(
        **{k: v for k, v in TestRunResponse.model_validate(run).model_dump().items()},
        test_cases=[TestCaseBrief.model_validate(c) for c in cases],
        test_results=[TestResultBrief.model_validate(r) for r in results],
    )
