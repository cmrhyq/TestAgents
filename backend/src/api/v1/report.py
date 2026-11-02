"""报告路由。"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.data.schemas.agent_run import AgentRunBrief
from src.data.schemas.agent_tool_call import AgentToolCallDetail
from src.data.schemas.report import (
    ReportDetailResponse,
    ReportListResponse,
    ReportResponse,
)
from src.data.services import ReportService

router = APIRouter(prefix="/reports", tags=["执行报告"])


@router.get("/", response_model=ReportListResponse)
def list_reports(
    run_id: int | None = Query(default=None, description="按执行记录 ID 筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """查询报告列表（分页）。"""
    page_items, total = ReportService(db).list_reports(run_id, page, page_size)

    items = [
        ReportResponse(
            id=report.id,
            run_id=report.run_id,
            format=report.format,
            file_path=report.file_path,
            file_size=report.file_size,
            generated_at=report.generated_at,
            run_title=run_title,
        )
        for report, run_title in page_items
    ]

    return ReportListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{report_id}", response_model=ReportDetailResponse)
def get_report_detail(report_id: int, db: Session = Depends(get_db)):
    """获取报告详情（含执行记录统计与工具调用留痕）。"""
    report, run, tool_calls = ReportService(db).get_detail(report_id)

    return ReportDetailResponse(
        id=report.id,
        run_id=report.run_id,
        format=report.format,
        file_size=report.file_size,
        generated_at=report.generated_at,
        run=AgentRunBrief.model_validate(run),
        tool_calls=[AgentToolCallDetail.model_validate(c) for c in tool_calls],
    )


@router.get("/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    """下载报告文件。"""
    report, file_path = ReportService(db).get_download_file(report_id)

    filename = f"agent_report_{report.run_id}.{report.format}"
    media_type = "text/html" if report.format == "html" else "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
